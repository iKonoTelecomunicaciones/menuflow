from __future__ import annotations

from json import JSONDecodeError
from logging import Logger, getLogger

from aiohttp import web

from ...config import Config
from ...db.flow import Flow as DBFlow
from ...db.module import Module as DBModule
from ...db.tag import Tag as DBTag
from ..base import get_config, routes
from ..docs.tag import delete_tag_doc, get_tags_by_flow_doc, publish_tag_doc, restore_tag_doc
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
        search = request.query.get("search")

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

            count = await DBTag.get_tags_count(flow_id, search=search)
            tags = await DBTag.get_flow_tags(flow_id, offset=offset, limit=limit, search=search)

            tags_list = [tag.to_dict() for tag in tags]

            log_msg = f"({uuid}) -> Returning {count} tags for flowId: {flow_id}"
            return resp.success(data={"count": count, "tags": tags_list}, log_msg=log_msg)

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

        if tag.active:
            return resp.conflict(f"Tag with ID {tag_id} is active and cannot be deleted", uuid)

        await DBModule.delete_modules_by_tag(tag_id)

        deleted = await tag.delete()
        if not deleted:
            return resp.server_error(f"Tag with ID {tag_id} could not be deleted", uuid)

        log.info(f"({uuid}) -> Tag with ID {tag_id} deleted successfully")
        return resp.ok({"message": f"Tag with ID {tag_id} deleted successfully"}, uuid)

    except ValueError:
        return resp.bad_request("tag_id must be a valid integer", uuid)
    except Exception as e:
        log.error(f"({uuid}) -> Error deleting tag: {e}", exc_info=True)
        return resp.server_error(str(e), uuid)


@routes.post("/v1/{flow_id}/tag_restore")
@Util.docstring(restore_tag_doc)
async def restore_tag(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Restoring tag")

    try:
        flow_id = int(request.match_info["flow_id"])
    except ValueError:
        return resp.bad_request("flow_id must be a valid integer", uuid)

    try:
        data = await request.json()
    except JSONDecodeError:
        return resp.bad_request("Invalid JSON in request body", uuid)

    source_tag_id = data.get("tag_id")
    if not source_tag_id:
        return resp.bad_request("tag_id is required", uuid)

    try:
        source_tag_id = int(source_tag_id)
    except (ValueError, TypeError):
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
    if source_tag.flow_id != flow_id:
        return resp.bad_request(
            f"Tag with ID {source_tag_id} does not belong to flow {flow_id}", uuid
        )

    # Create new current tag
    new_current_tag = DBTag(
        flow_id=flow_id,
        name="current",
        author="system",
        active=False,
        flow_vars=source_tag.flow_vars,
    )
    new_current_tag_id = await new_current_tag.insert()

    # Copy modules from source tag to new current tag
    copy_result = await DBModule.copy_modules_from_tag(source_tag_id, new_current_tag_id)

    if not copy_result.get("success"):
        return resp.server_error(f"Error copying modules: {copy_result.get('error')}", uuid)

    # Delete modules from current_temp tag and delete current_temp tag
    log.info(f"({uuid}) -> Deleting current_temp tag")
    await DBModule.delete_modules_by_tag(current_tag.id)
    await current_tag.delete()

    return resp.ok({"message": "Tag restored successfully"}, uuid)


@routes.post("/v1/{flow_id}/publish/{tag_id}")
@Util.docstring(publish_tag_doc)
async def publish_tag(request: web.Request) -> web.Response:
    uuid = Util.generate_uuid()
    log.info(f"({uuid}) -> '{request.method}' '{request.path}' Publishing tag")

    try:
        flow_id = int(request.match_info["flow_id"])
        tag_id = int(request.match_info["tag_id"])
    except ValueError:
        return resp.bad_request("flow_id and tag_id must be valid integers", uuid)

    try:
        tag = await DBTag.get_by_id(tag_id)
        if tag.active:
            return resp.conflict(f"Tag with ID {tag_id} is active and cannot be published", uuid)

        await DBTag.deactivate_tags(flow_id)
        await DBTag.activate_tag(tag_id)

        # Restart flow
        config: Config = get_config()
        if config["menuflow.load_flow_from"] == "database":
            modules = await DBModule.get_tag_modules(tag_id)
            nodes = [node for module in modules for node in module.nodes]
            await Util.update_flow_db_clients(
                flow_id, {"flow_variables": tag.flow_vars, "nodes": nodes}, config
            )

        log.info(f"({uuid}) -> Tag {tag_id} published successfully for flow {flow_id}")
        return resp.ok({"message": "Tag published successfully"}, uuid)

    except Exception as e:
        log.error(f"({uuid}) -> Error publishing tag: {e}", exc_info=True)
        return resp.server_error(str(e), uuid)
