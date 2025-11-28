"""
Meta Flow Encryption Module

This module provides encryption and decryption functionality for Meta flow requests and responses.
"""

from __future__ import annotations

import base64
import json
from logging import Logger, getLogger
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asymmetric_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

log: Logger = getLogger("menuflow.utils.encryption")


class FlowEndpointException(Exception):
    """Exception for Flow Endpoint errors"""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class MetaFlowEncryption:
    """Handles encryption and decryption for Meta Flow requests and responses"""

    @staticmethod
    def decrypt_request(
        body: dict[str, Any], private_pem: str, passphrase: str | None = None
    ) -> dict[str, Any]:
        """
        Decrypts an encrypted request from Meta.

        Parameters
        ----------
        body : Dict[str, Any]
            The encrypted request body containing:
            - encrypted_aes_key: Base64 encoded encrypted AES key
            - encrypted_flow_data: Base64 encoded encrypted flow data
            - initial_vector: Base64 encoded initial vector
        private_pem : str
            The private key in PEM format
        passphrase : str | None, optional
            The passphrase for the private key, if any

        Returns
        -------
        dict[str, Any]
            Dictionary containing:
            - decrypted_body: The decrypted JSON data as dict
            - aes_key_buffer: The decrypted AES key as bytes
            - initial_vector_buffer: The initial vector as bytes

        Raises
        ------
        FlowEndpointException
            If decryption fails (status 421 to refresh public key)
        """
        try:
            encrypted_aes_key = body["encrypted_aes_key"]
            encrypted_flow_data = body["encrypted_flow_data"]
            initial_vector = body["initial_vector"]
        except KeyError as e:
            raise FlowEndpointException(400, f"Missing required field: {e}")

        # Load the private key
        try:
            private_key = serialization.load_pem_private_key(
                private_pem.encode("utf-8"),
                password=passphrase.encode("utf-8") if passphrase else None,
                backend=default_backend(),
            )
        except Exception as e:
            log.error(f"Failed to load private key: {e}")
            raise FlowEndpointException(421, "Failed to load private key")

        # Decrypt AES key created by client
        try:
            encrypted_aes_key_bytes = base64.b64decode(encrypted_aes_key)
            decrypted_aes_key = private_key.decrypt(
                encrypted_aes_key_bytes,
                asymmetric_padding.OAEP(
                    mgf=asymmetric_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        except Exception as e:
            log.error(f"Failed to decrypt AES key: {e}")
            raise FlowEndpointException(
                421, "Failed to decrypt the request. Please verify your private key."
            )

        # Decrypt flow data
        try:
            flow_data_buffer = base64.b64decode(encrypted_flow_data)
            initial_vector_buffer = base64.b64decode(initial_vector)

            TAG_LENGTH = 16
            encrypted_flow_data_body = flow_data_buffer[:-TAG_LENGTH]
            encrypted_flow_data_tag = flow_data_buffer[-TAG_LENGTH:]

            # Create cipher for AES-128-GCM
            cipher = Cipher(
                algorithms.AES(decrypted_aes_key),
                modes.GCM(initial_vector_buffer, encrypted_flow_data_tag),
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()

            decrypted_data = decryptor.update(encrypted_flow_data_body) + decryptor.finalize()
            decrypted_json_string = decrypted_data.decode("utf-8")

            return {
                "decrypted_body": json.loads(decrypted_json_string),
                "aes_key_buffer": decrypted_aes_key,
                "initial_vector_buffer": initial_vector_buffer,
            }

        except Exception as e:
            log.error(f"Failed to decrypt flow data: {e}")
            raise FlowEndpointException(421, "Failed to decrypt flow data")

    @staticmethod
    def encrypt_response(
        response: dict[str, Any], aes_key_buffer: bytes, initial_vector_buffer: bytes
    ) -> str:
        """
        Encrypts a response to be sent back to Meta.

        Parameters
        ----------
        response : Dict[str, Any]
            The response data to encrypt
        aes_key_buffer : bytes
            The AES key used for encryption
        initial_vector_buffer : bytes
            The initial vector from the request

        Returns
        -------
        str
            Base64 encoded encrypted response
        """
        try:
            # Flip initial vector (bitwise NOT operation)
            flipped_iv = bytes(~byte & 0xFF for byte in initial_vector_buffer)

            # Convert response to JSON string
            response_json = json.dumps(response, separators=(",", ":"))

            # Create cipher for AES-128-GCM
            cipher = Cipher(
                algorithms.AES(aes_key_buffer), modes.GCM(flipped_iv), backend=default_backend()
            )
            encryptor = cipher.encryptor()

            # Encrypt the response
            encrypted_data = encryptor.update(response_json.encode("utf-8")) + encryptor.finalize()

            # Combine encrypted data with auth tag
            encrypted_response = encrypted_data + encryptor.tag

            return base64.b64encode(encrypted_response).decode("utf-8")

        except Exception as e:
            log.error(f"Failed to encrypt response: {e}")
            raise FlowEndpointException(500, "Failed to encrypt response")

    @staticmethod
    def generate_key_pair() -> tuple[str, str]:
        """
        Generates a new RSA key pair for testing purposes.

        Returns
        -------
        Tuple[str, str]
            A tuple containing (private_key_pem, public_key_pem)
        """
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

        # Get public key
        public_key = private_key.public_key()

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        return private_pem, public_pem
