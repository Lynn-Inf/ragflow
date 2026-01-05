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
from quart import request
from api.apps import login_required
from api.apps.services.memory_services import MessageManager

from api.utils.api_utils import validate_request, get_request_json, get_error_argument_result


@manager.route("", methods=["POST"]) # noqa: F821
@login_required
@validate_request("memory_id", "agent_id", "session_id", "user_input", "agent_response")
async def add_message():

    req = await get_request_json()
    memory_ids = req["memory_id"]
    message_dict = {
        "user_id": req["agent_id"],
        "agent_id": req["session_id"],
        "session_id": req["user_id"] if req.get("user_id") else "",
        "user_input": req["user_input"],
        "agent_response": req["agent_response"]
    }

    return await MessageManager.add_message(memory_ids, message_dict)


@manager.route("/<memory_id>:<message_id>", methods=["DELETE"]) # noqa: F821
@login_required
async def forget_message(memory_id: str, message_id: int):
    return await MessageManager.forget_message(memory_id, message_id)


@manager.route("/<memory_id>:<message_id>", methods=["PUT"]) # noqa: F821
@login_required
@validate_request("status")
async def update_message(memory_id: str, message_id: int):
    req = await get_request_json()
    status = req["status"]
    return await MessageManager.update_message_status(memory_id, message_id, status)


@manager.route("/search", methods=["GET"]) # noqa: F821
@login_required
async def search_message():
    args = request.args
    empty_fields = [f for f in ["memory_id", "query"] if not args.get(f)]
    if empty_fields:
        return get_error_argument_result(f"{', '.join(empty_fields)} can't be empty.")

    filter_dict = {
        "memory_id": args.getlist("memory_id"),
        "agent_id": args.get("agent_id", ""),
        "session_id": args.get("session_id", "")
    }
    params = {
        "query": args.get("query"),
        "similarity_threshold": float(args.get("similarity_threshold", 0.2)),
        "keywords_similarity_weight": float(args.get("keywords_similarity_weight", 0.7)),
        "top_n": int(args.get("top_n", 5))
    }
    return MessageManager.search_message(filter_dict, params)


@manager.route("", methods=["GET"]) # noqa: F821
@login_required
async def get_messages():
    args = request.args
    memory_ids = args.getlist("memory_id")
    agent_id = args.get("agent_id", "")
    session_id = args.get("session_id", "")
    limit = int(args.get("limit", 10))
    return await MessageManager.get_recent_messages(memory_ids, agent_id, session_id, limit)

@manager.route("/<memory_id>:<message_id>/content", methods=["GET"]) # noqa: F821
@login_required
async def get_message_content(memory_id:str, message_id: int):
   return await MessageManager.get_message_content(memory_id, message_id)