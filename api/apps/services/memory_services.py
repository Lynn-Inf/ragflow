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
from api.apps import current_user
from api.db import TenantPermission
from api.db.services.memory_service import MemoryService
from api.db.services.canvas_service import UserCanvasService
from api.db.services.task_service import TaskService
from api.db.services.user_service import UserTenantService
from api.db.joint_services.memory_message_service import get_memory_size_cache, judge_system_prompt_is_default, query_message, queue_save_to_memory_task
from api.utils.api_utils import get_error_argument_result, get_json_result
from api.utils.memory_utils import format_ret_data_from_memory, get_memory_type_human
from api.constants import MEMORY_NAME_LIMIT, MEMORY_SIZE_LIMIT
from memory.services.messages import MessageService
from memory.utils.prompt_util import PromptAssembler
from common.constants import MemoryType, RetCode, ForgettingPolicy
from common.time_utils import current_timestamp, timestamp_to_date

class MemoryManager:

    @staticmethod
    def create_memory(tenant_id: str, memory_name: str, memory_type: list[str], embd_id: str, llm_id: str):
        # check name length
        memory_name = memory_name.strip()
        if len(memory_name) == 0:
            return get_error_argument_result("Memory name cannot be empty or whitespace.")
        if len(memory_name) > MEMORY_NAME_LIMIT:
            return get_error_argument_result(f"Memory name '{memory_name}' exceeds limit of {MEMORY_NAME_LIMIT}.")
        # check memory_type valid
        memory_type = set(memory_type)
        invalid_type = memory_type - {e.name.lower() for e in MemoryType}
        if invalid_type:
            return get_error_argument_result(f"Memory type '{invalid_type}' is not supported.")
        memory_type = list(memory_type)

        try:
            res, memory = MemoryService.create_memory(
                tenant_id=tenant_id,
                name=memory_name,
                memory_type=memory_type,
                embd_id=embd_id,
                llm_id=llm_id
            )

            if res:
                return get_json_result(message=True, data=format_ret_data_from_memory(memory))
            else:
                return get_json_result(message=memory, code=RetCode.SERVER_ERROR)

        except Exception as e:
            return get_json_result(message=str(e), code=RetCode.SERVER_ERROR)

    @staticmethod
    def update_memory(memory_id:str, new_config: dict):
        update_dict = {}
        # check name length
        if "name" in new_config:
            name = new_config["name"]
            memory_name = name.strip()
            if len(memory_name) == 0:
                return get_error_argument_result("Memory name cannot be empty or whitespace.")
            if len(memory_name) > MEMORY_NAME_LIMIT:
                return get_error_argument_result(f"Memory name '{memory_name}' exceeds limit of {MEMORY_NAME_LIMIT}.")
            update_dict["name"] = memory_name
        # check permissions valid
        if new_config.get("permissions"):
            if new_config["permissions"] not in [e.value for e in TenantPermission]:
                return get_error_argument_result(f"Unknown permission '{new_config['permissions']}'.")
            update_dict["permissions"] = new_config["permissions"]
        if new_config.get("llm_id"):
            update_dict["llm_id"] = new_config["llm_id"]
        if new_config.get("embd_id"):
            update_dict["embd_id"] = new_config["embd_id"]
        if new_config.get("memory_type"):
            memory_type = set(new_config["memory_type"])
            invalid_type = memory_type - {e.name.lower() for e in MemoryType}
            if invalid_type:
                return get_error_argument_result(f"Memory type '{invalid_type}' is not supported.")
            update_dict["memory_type"] = list(memory_type)
        # check memory_size valid
        if new_config.get("memory_size"):
            if not 0 < int(new_config["memory_size"]) <= MEMORY_SIZE_LIMIT:
                return get_error_argument_result(f"Memory size should be in range (0, {MEMORY_SIZE_LIMIT}] Bytes.")
            update_dict["memory_size"] = new_config["memory_size"]
        # check forgetting_policy valid
        if new_config.get("forgetting_policy"):
            if new_config["forgetting_policy"] not in [e.value for e in ForgettingPolicy]:
                return get_error_argument_result(f"Forgetting policy '{new_config['forgetting_policy']}' is not supported.")
            update_dict["forgetting_policy"] = new_config["forgetting_policy"]
        # check temperature valid
        if "temperature" in new_config:
            temperature = float(new_config["temperature"])
            if not 0 <= temperature <= 1:
                return get_error_argument_result("Temperature should be in range [0, 1].")
            update_dict["temperature"] = temperature
        # allow update to empty fields
        for field in ["avatar", "description", "system_prompt", "user_prompt"]:
            if field in new_config:
                update_dict[field] = new_config[field]
        current_memory = MemoryService.get_by_memory_id(memory_id)
        if not current_memory:
            return get_json_result(code=RetCode.NOT_FOUND, message=f"Memory '{memory_id}' not found.")

        memory_dict = current_memory.to_dict()
        memory_dict.update({"memory_type": get_memory_type_human(current_memory.memory_type)})
        to_update = {}
        for k, v in update_dict.items():
            if isinstance(v, list) and set(memory_dict[k]) != set(v):
                to_update[k] = v
            elif memory_dict[k] != v:
                to_update[k] = v

        if not to_update:
            return get_json_result(message=True, data=memory_dict)
        # check memory empty when update embd_id, memory_type
        memory_size = get_memory_size_cache(memory_id, current_memory.tenant_id)
        not_allowed_update = [f for f in ["embd_id", "memory_type"] if f in to_update and memory_size > 0]
        if not_allowed_update:
            return get_error_argument_result(f"Can't update {not_allowed_update} when memory isn't empty.")
        if "memory_type" in to_update:
            if "system_prompt" not in to_update and judge_system_prompt_is_default(current_memory.system_prompt,
                                                                                   current_memory.memory_type):
                # update old default prompt, assemble a new one
                to_update["system_prompt"] = PromptAssembler.assemble_system_prompt(
                    {"memory_type": to_update["memory_type"]})

        try:
            MemoryService.update_memory(current_memory.tenant_id, memory_id, to_update)
            updated_memory = MemoryService.get_by_memory_id(memory_id)
            return get_json_result(message=True, data=format_ret_data_from_memory(updated_memory))

        except Exception as e:
            logging.error(e)
            return get_json_result(message=str(e), code=RetCode.SERVER_ERROR)

    @staticmethod
    def delete_memory(memory_id):
        memory = MemoryService.get_by_memory_id(memory_id)
        if not memory:
            return get_json_result(message=True, code=RetCode.NOT_FOUND)
        try:
            MemoryService.delete_memory(memory_id)
            if MessageService.has_index(memory.tenant_id, memory_id):
                MessageService.delete_message({"memory_id": memory_id}, memory.tenant_id, memory_id)
            return get_json_result(message=True)
        except Exception as e:
            logging.error(e)
            return get_json_result(message=str(e), code=RetCode.SERVER_ERROR)

    @staticmethod
    def list_memory(filter_dict, keywords: str, page: int, page_size: int):
        if not filter_dict.get("tenant_id"):
            # restrict to current user's tenants
            user_tenants = UserTenantService.get_user_tenant_relation_by_user_id(current_user.id)
            filter_dict["tenant_id"] = [tenant["tenant_id"] for tenant in user_tenants]
        memory_list, count = MemoryService.get_by_filter(filter_dict, keywords, page, page_size)
        [memory.update({"memory_type": get_memory_type_human(memory["memory_type"])}) for memory in memory_list]
        return get_json_result(message=True, data={"memory_list": memory_list, "total_count": count})

    @staticmethod
    def get_memory_config(memory_id: str):
        memory = MemoryService.get_with_owner_name_by_id(memory_id)
        if not memory:
            return get_json_result(code=RetCode.NOT_FOUND, message=f"Memory '{memory_id}' not found.")
        return get_json_result(message=True, data=format_ret_data_from_memory(memory))


class MessageManager:

    @staticmethod
    def list_memory_message(memory_id: str, agent_ids: list[str], keywords: str, page: int, page_size: int):
        memory = MemoryService.get_by_memory_id(memory_id)
        if not memory:
            return get_json_result(code=RetCode.NOT_FOUND, message=f"Memory '{memory_id}' not found.")
        messages = MessageService.list_message(
            memory.tenant_id, memory_id, agent_ids, keywords, page, page_size)
        agent_name_mapping = {}
        extract_task_mapping = {}
        if messages["message_list"]:
            agent_list = UserCanvasService.get_basic_info_by_canvas_ids(
                [message["agent_id"] for message in messages["message_list"]])
            agent_name_mapping = {agent["id"]: agent["title"] for agent in agent_list}
            task_list = TaskService.get_tasks_progress_by_doc_ids([memory_id])
            if task_list:
                task_list.sort(key=lambda t: t["create_time"])  # asc, use newer when exist more than one task
                for task in task_list:
                    # the 'digest' field carries the source_id when a task is created, so use 'digest' as key
                    extract_task_mapping.update({int(task["digest"]): task})
        for message in messages["message_list"]:
            message["agent_name"] = agent_name_mapping.get(message["agent_id"], "Unknown")
            message["task"] = extract_task_mapping.get(message["message_id"], {})
        return get_json_result(data={"messages": messages, "storage_type": memory.storage_type}, message=True)

    @staticmethod
    async def add_message(memory_ids: list[str], message_dict: dict):
        if not memory_ids:
            return get_json_result(message="No memory selected.")
        res, msg = await queue_save_to_memory_task(memory_ids, message_dict)
        if res:
            return get_json_result(message=msg)
        else:
            return get_json_result(message=msg, code=RetCode.SERVER_ERROR)

    @staticmethod
    async def forget_message(memory_id: str, message_id: int):

        memory = MemoryService.get_by_memory_id(memory_id)
        if not memory:
            return get_json_result(code=RetCode.NOT_FOUND, message=f"Memory '{memory_id}' not found.")

        forget_time = timestamp_to_date(current_timestamp())
        update_succeed = MessageService.update_message(
            {"memory_id": memory_id, "message_id": int(message_id)},
            {"forget_at": forget_time},
            memory.tenant_id, memory_id)
        if update_succeed:
            return get_json_result(message=update_succeed)
        else:
            return get_json_result(code=RetCode.SERVER_ERROR,
                                   message=f"Failed to forget message '{message_id}' in memory '{memory_id}'.")

    @staticmethod
    async def update_message_status(memory_id: str, message_id: int, status: bool):
        if not isinstance(status, bool):
            return get_error_argument_result("Status must be a boolean.")

        memory = MemoryService.get_by_memory_id(memory_id)
        if not memory:
            return get_json_result(code=RetCode.NOT_FOUND, message=f"Memory '{memory_id}' not found.")

        update_succeed = MessageService.update_message({"memory_id": memory_id, "message_id": int(message_id)},
                                                       {"status": status}, memory.tenant_id, memory_id)
        if update_succeed:
            return get_json_result(message=update_succeed)
        else:
            return get_json_result(code=RetCode.SERVER_ERROR,
                                   message=f"Failed to set status for message '{message_id}' in memory '{memory_id}'.")

    @staticmethod
    async def search_message(filter_dict: dict, params: dict):
        res = query_message(filter_dict, params)
        return get_json_result(message=True, data=res)

    @staticmethod
    async def get_recent_messages(memory_ids: list[str], agent_id: str, session_id: str, limit: int):
        if not memory_ids:
            return get_error_argument_result("memory_ids is required.")
        memory_list = MemoryService.get_by_ids(memory_ids)
        uids = [memory.tenant_id for memory in memory_list]
        res = MessageService.get_recent_messages(uids, memory_ids,agent_id, session_id, limit)
        return get_json_result(message=True, data=res)

    @staticmethod
    async def get_message_content(memory_id: str, message_id: int):
        memory = MemoryService.get_by_memory_id(memory_id)
        if not memory:
            return get_json_result(code=RetCode.NOT_FOUND, message=f"Memory '{memory_id}' not found.")

        res = MessageService.get_by_message_id(memory_id, message_id, memory.tenant_id)
        if res:
            return get_json_result(message=True, data=res)
        else:
            return get_json_result(code=RetCode.NOT_FOUND,
                                   message=f"Message '{message_id}' in memory '{memory_id}' not found.")
