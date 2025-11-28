# Meta Dynamic Flows

This document explains how to use the Meta dynamic flows system implemented in MenuFlow.

## Overview

The dynamic flows system allows Meta to handle conversational flows that change dynamically based on user responses. Information is obtained from different APIs through HTTP nodes and the flow adjusts according to context.

## Implemented Components

### 1. Encryption Module (`menuflow/utils/encryption.py`)

Implements encryption and decryption functions based on Meta's official example:

- `decrypt_request()`: Decrypts Meta requests using RSA + AES-128-GCM
- `encrypt_response()`: Encrypts responses for Meta
- `generate_key_pair()`: Generates RSA key pairs for testing

### 2. API Endpoint (`menuflow/web/api/meta.py`)

Main endpoint: `POST /v1/meta/{mxid}`

**Processing flow:**
1. Decrypts the Meta request
2. Extracts `room_id` from the request body
3. Finds/creates the corresponding room
4. Gets or initializes the `flow_screen` variable
5. Executes the corresponding flow node
6. Updates `flow_screen` with the next node
7. Encrypts and returns the response

### 3. Configuration

The following configurations were added to `menuflow/example-config.yaml`:

```yaml
meta:
  private_key: # Your meta key here

  private_key_passphrase: "your_passphrase"
```

## Initial Setup

### 1. Generate RSA Keys

```bash
# Generate encrypted private key
openssl genpkey -algorithm RSA -out private_key.pem -pkcs8 -aes256

# Extract public key
openssl rsa -in private_key.pem -pubout -out public_key.pem
```

### 2. Configure Keys

Copy the key contents to your configuration file:

```yaml
meta:
  private_key: # content of private_key.pem

  private_key_passphrase: "your_passphrase"
```

Then follow [these steps to upload the key pair](https://developers.facebook.com/docs/whatsapp/flows/guides/implementingyourflowendpoint#upload_public_key)
to your business phone number.

### 3. Install Dependencies

Make sure to install the `cryptography` library:

```bash
pip install cryptography==41.0.7
```

## System Usage

### 1. `flow_screen` Variable

The system uses a room variable called `flow_screen` that:
- Stores the current node ID in the flow
- Is automatically initialized with the first flow node if it doesn't exist
- Is updated after each node execution

### 2. Request Structure

Meta will send encrypted requests with the following structure (after decryption):

Ensure that you send via message the room_id and the mxid of the room in the meta flow

```json
{
  "room_id": "!example:domain.com",
  "mxid": "@menubot1:domain.com",
  "data": { ... },
  "screen": "screen_name",
  "action": "data_exchange",
  "version": "3.0"
}
```

### 3. Response Structure

The system returns encrypted responses with this structure:

```json
{
  "screen": "next_node_id",
  "data": { ... }
}
```

## Troubleshooting

### Error 421 - Failed to decrypt

- Verify that the private key is correctly configured
- Ensure the passphrase is correct
- Confirm that Meta is using the corresponding public key

### Error 404 - Client not found

- Verify that the `mxid` in the URL corresponds to an active client
- Ensure the client is enabled

### Error 500 - Node execution failed

- Review logs for specific node errors
- Verify that the flow is correctly configured
- Ensure necessary variables are defined
