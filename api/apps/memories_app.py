#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging

from quart import request
from api.apps import login_required, current_user
from api.apps.services.memory_services import MemoryManager, MessageManager
from api.utils.api_utils import validate_request, get_request_json, get_json_result
from common.constants import RetCode


@manager.route("", methods=["POST"])  # noqa: F821
@login_required
@validate_request("name", "memory_type", "embd_id", "llm_id")
async def create_memory():
    req = await get_request_json()
    return MemoryManager.create_memory(current_user.id, req["name"], req["memory_type"], req["embd_id"], req["llm_id"])


@manager.route("/<memory_id>", methods=["PUT"])  # noqa: F821
@login_required
async def update_memory(memory_id):
    req = await get_request_json()
    return MemoryManager.update_memory(memory_id, req)


@manager.route("/<memory_id>", methods=["DELETE"])  # noqa: F821
@login_required
async def delete_memory(memory_id):
    return MemoryManager.delete_memory(memory_id)


@manager.route("", methods=["GET"])  # noqa: F821
@login_required
async def list_memory():
    args = request.args
    try:
        tenant_ids = args.getlist("tenant_id")
        memory_types = args.getlist("memory_type")
        storage_type = args.get("storage_type")
        keywords = args.get("keywords", "")
        page = int(args.get("page", 1))
        page_size = int(args.get("page_size", 50))
        # make filter dict
        filter_dict = {"memory_type": memory_types, "storage_type": storage_type, "tenant_id": tenant_ids}
        return MemoryManager.list_memory(filter_dict, keywords, page, page_size)

    except Exception as e:
        logging.error(e)
        return get_json_result(message=str(e), code=RetCode.SERVER_ERROR)


@manager.route("/<memory_id>/config", methods=["GET"])  # noqa: F821
@login_required
async def get_memory_config(memory_id):
    return MemoryManager.get_memory_config(memory_id)


@manager.route("/<memory_id>", methods=["GET"])  # noqa: F821
@login_required
async def get_memory_detail(memory_id):
    args = request.args
    agent_ids = args.getlist("agent_id")
    keywords = args.get("keywords", "")
    keywords = keywords.strip()
    page = int(args.get("page", 1))
    page_size = int(args.get("page_size", 50))
    return MessageManager.list_memory_message(memory_id, agent_ids, keywords, page, page_size)
