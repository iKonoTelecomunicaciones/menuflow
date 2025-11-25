from __future__ import annotations

from json import JSONDecodeError
from logging import Logger, getLogger

from aiohttp import web

from ...config import Config
from ...db.flow import Flow as DBFlow
from ...db.tag import Tag as DBTag
from ..base import routes
from ..docs.tag import delete_tag_doc, get_tags_by_flow_doc
from ..responses import resp
from ..util import Util

log: Logger = getLogger("menuflow.web.api.tag")


@routes.get("/v1/{flow_id}/tag", allow_head=False)
@Util.docstring(get_tags_by_flow_doc)
async def get_tags_by_flow(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting tags")

    try:
        flow_id = int(request.match_info["flow_id"])
        tag_id = request.query.get("id")
        tag_name = request.query.get("name")

        if tag_id:
            try:
                id = int(tag_id)
            except ValueError:
                return resp.bad_request("tag_id must be a valid integer", uuid)

            tag = await DBTag.get_by_id(id)
            if not tag:
                return resp.not_found(f"Tag with ID {id} not found", uuid)

            return resp.ok(tag.to_dict(), uuid)
        elif tag_name:
            log.debug(f"({uuid}) -> Getting tag '{tag_name}' for flow_id: {flow_id}")
            tag = await DBTag.get_by_name(flow_id, tag_name)
            if not tag:
                return resp.not_found(
                    f"Tag with name '{tag_name}' not found for flow_id {flow_id}", uuid
                )

            return resp.ok(tag.to_dict(), uuid)

        else:
            log.debug(f"({uuid}) -> Getting all tags for flow_id: {flow_id}")
            tags = await DBTag.get_flow_tags(flow_id)
            if not tags:
                return resp.not_found(f"No tags found for flow_id {flow_id}", uuid)

            tags_list = [tag.to_dict() for tag in tags]
            return resp.ok({"tags": tags_list}, uuid)

    except ValueError:
        return resp.bad_request("flow_id must be a valid integer", uuid)
    except Exception as e:
        log.error(f"({uuid}) -> Error getting tags: {e}", exc_info=True)
        return resp.server_error(str(e), uuid)


@routes.delete("/v1/tag/{tag_id}")
@Util.docstring(delete_tag_doc)
async def delete_tag(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Deleting tag")

    try:
        tag_id = int(request.match_info["tag_id"])
        tag = await DBTag.get_by_id(tag_id)
        if not tag:
            return resp.not_found(f"Tag with ID {tag_id} not found", uuid)

        deleted = await tag.delete()
        if not deleted:
            return resp.conflict(f"Tag with ID {tag_id} is active and cannot be deleted", uuid)

        log.info(f"({uuid}) -> Tag with ID {tag_id} deleted successfully")
        return resp.ok({"message": f"Tag with ID {tag_id} deleted successfully"}, uuid)

    except ValueError:
        return resp.bad_request("tag_id must be a valid integer", uuid)
    except Exception as e:
        log.error(f"({uuid}) -> Error deleting tag: {e}", exc_info=True)
        return resp.server_error(str(e), uuid)
