from __future__ import annotations

from json import JSONDecodeError
from logging import Logger, getLogger

from aiohttp import web

from ...config import Config
from ...db.flow import Flow as DBFlow
from ...db.module import Module as DBModule
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
            try:
                offset = int(request.query.get("offset", 0))
                limit = int(request.query.get("limit", 10))
            except ValueError:
                return resp.bad_request("offset and limit must be valid integers", uuid)

            count = await DBTag.get_tags_count(flow_id)
            tags = await DBTag.get_flow_tags(flow_id, offset=offset, limit=limit)

            tags_list = [tag.to_dict() for tag in tags]
            return resp.ok({"count": count, "tags": tags_list}, uuid)

    except ValueError:
        return resp.bad_request("flow_id must be a valid integer", uuid)
    except Exception as e:
        log.error(f"({uuid}) -> Error getting tags: {e}", exc_info=True)
        return resp.server_error(str(e), uuid)


@routes.get("/v1/{flow_id}/flow_vars")
async def get_flow_vars(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Getting flow vars")

    flow_id = int(request.match_info["flow_id"])
    tag_id = request.query.get("tag_id")

    if tag_id:
        try:
            tag_id = int(tag_id)
        except ValueError:
            return resp.bad_request("tag_id must be a valid integer", uuid)

        tag = await DBTag.get_by_id(tag_id)
        if not tag:
            return resp.not_found(f"Tag with ID {tag_id} not found", uuid)
    else:
        tag = await DBTag.get_current_tag(flow_id)
        if not tag:
            return resp.not_found(f"Current tag for flow {flow_id} not found", uuid)

    log_msg = f"Returning flow vars for tag: {tag.id}"
    return resp.success(data={"flow_vars": tag.flow_vars}, log_msg=log_msg)


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


@routes.post("/v1/{flow_id}/tag/restore")
async def restore_tag(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Restoring tag")

    try:
        flow_id = int(request.match_info["flow_id"])
    except ValueError:
        return resp.bad_request("flow_id must be a valid integer", uuid)

    source_tag_id = request.query.get("tag_id")
    if not source_tag_id:
        return resp.bad_request("tag_id is required", uuid)

    try:
        source_tag_id = int(source_tag_id)
    except ValueError:
        return resp.bad_request("tag_id must be a valid integer", uuid)

    # Get the current tag
    current_tag = await DBTag.get_current_tag(flow_id)
    if not current_tag:
        return resp.not_found(f"Current tag for flow {flow_id} not found", uuid)

    # Rename current tag to current_temp
    log.info(f"({uuid}) -> Renaming current tag to current_temp")
    current_tag.name = "current_temp"
    await current_tag.update()

    # Get source tag to copy flow_vars
    source_tag = await DBTag.get_by_id(source_tag_id)
    if not source_tag:
        return resp.not_found(f"Tag with ID {source_tag_id} not found", uuid)

    # Create new current tag
    log.info(f"({uuid}) -> Creating new current tag")
    new_current_tag = DBTag(
        flow_id=flow_id,
        name="current",
        author="system",
        active=False,
        flow_vars=source_tag.flow_vars,
    )
    new_current_tag_id = await new_current_tag.insert()

    # Copy modules from source tag to new current tag
    log.info(f"({uuid}) -> Copying modules from tag {source_tag_id} to new current tag")
    copy_result = await DBModule.copy_modules_from_tag(source_tag_id, new_current_tag_id)

    if not copy_result.get("success"):
        return resp.server_error(f"Error copying modules: {copy_result.get('error')}", uuid)

    # Delete modules from current_temp tag and delete current_temp tag
    log.info(f"({uuid}) -> Deleting current_temp tag")
    await DBModule.delete_modules_by_tag(current_tag.id)
    await current_tag.delete()

    return resp.ok({"message": "Tag restored successfully"}, uuid)
