# import asyncio
# from http import HTTPStatus
# from typing import Dict, List

# import httpx

# from src.common.conf.setting import setting

# from .blocks import Button, Buttons, Divider, MrkDwn
# from .constants import Domain


# async def send_slack_message_with_thread(
#     url: str,
#     full_message: str
# ):
#     """긴 메시지를 스레드로 나누어 전송하는 함수"""
#     # 첫 1000자 자르기
#     initial_message = full_message[:1000]
#     remaining_message = full_message[1000:]

#     # 첫 번째 메시지 전송
#     payload = {
#         "text": initial_message
#     }

#     async with httpx.AsyncClient() as client:
#         response = await client.post(url, json=payload)
#         response.raise_for_status()

#         response_data = response.json()
#         thread_ts = response_data.get("ts")  # 첫 번째 메시지의 timestamp 가져오기

#     # 남은 메시지 스레드로 전송
#     if remaining_message:
#         while remaining_message:
#             thread_payload = {
#                 "text": remaining_message[:1000],  # 1000자씩 전송
#                 "thread_ts": thread_ts
#             }
#             await client.post(url, json=thread_payload)
#             remaining_message = remaining_message[1000:]


# async def _backup_message_send(
#     title: str,
#     mentions: List[str],
#     message: str,
#     url: str = ""
# ):
#     try:
#         # 발송 실패시 백업으로 hook url 사용
#         payload: Dict = {
#             'text': f"[임시 발송] {title}",
#             'blocks': [
#                 {
#                     'type': "header",
#                     'text': {
#                         'type': "plain_text",
#                         'text': f"{title}",
#                         'emoji': True,
#                     },
#                 },
#                 {
#                     'type': "section",
#                     'text': {
#                         'type': "mrkdwn",
#                         'text': (
#                             ", ".join(
#                                 [f"<@{_id}>" for _id in mentions]
#                             )
#                         ),
#                     },
#                 },
#                 {
#                     'type': "section",
#                     'text': {
#                         'type': "mrkdwn",
#                         'text': f"```{message}```",
#                     },
#                 }
#             ],
#         }
#         async with httpx.AsyncClient() as session:
#             response = await session.post(
#                 url=url,
#                 json=payload,
#             )
#             response.raise_for_status()
#             return True
#     except:
#         return False


# async def send_alarm(
#     level: str,
#     title: str,
#     url: str = "",
#     messages: List[str] = [],
#     extra_blocks: List[Dict] = [],
#     mentions: List[str] = [],
#     send_new_thread: bool = False,
#     filter_message: bool = False,
#     try_cnt: int = 3,
# ):
#     mentions_text = ", ".join([f"<@{mention}>" for mention in mentions])
#     messages_text = "\n\n".join(messages)

#     last_exc: Exception | None = None
#     for _ in range(try_cnt):
#         try:
#             async with httpx.AsyncClient() as session:
#                 endpoint = "slack-error-alarm"
#                 stop_url = f"{setting.HOTPARTNERS_API}/{endpoint}?is_active=false"
#                 reset_url = f"{setting.HOTPARTNERS_API}/{endpoint}?is_active=true"

#                 payload = {
#                     "blocks": [
#                         MrkDwn(text=f"*{title}*").payload,
#                         Divider().payload,
#                         MrkDwn(text=f"```{mentions_text}\n\n{messages_text}```").payload,
#                         Buttons(
#                             blocks=[
#                                 Button(text="Stop", url=stop_url),
#                                 Button(text="Reset", url=reset_url)
#                             ]
#                         ).payload,
#                         *extra_blocks,
#                     ]
#                 }

#                 response = await session.post(
#                     url=url,
#                     timeout=10,
#                     json=payload
#                 )

#                 if response.status_code == 200:
#                         response_json = response.json()
#                         return response_json
#                 elif response.status_code == 429:
#                         retry_after = int(response.headers.get("Retry-After", 1))
#                         await asyncio.sleep(retry_after)
#                 else:
#                     response.raise_for_status()
#         except httpx.HTTPStatusError as e:
#             last_exc = e
#             await asyncio.sleep(1)
#         except ValueError as e:
#             print("JSON decoding error:", e)
#             print("Response text was not JSON:", response.text)
#             return None

#     backup_send_result: bool = await _backup_message_send(
#         title=title,
#         mentions=mentions,
#         message="\n".join(messages),
#     )
#     if backup_send_result:
#         return

#     raise Exception(f"Failed to send Slack message. ({last_exc})")


# async def send_alarm_to_thread(
#     logger,
#     level: str,
#     channel_id: str,
#     title: str,
#     messages: List[str] = [],
#     extra_blocks: List[Dict] = [],
#     mentions: List[str] = [],
#     send_new_thread: bool = True,
#     filter_message: bool = False,
#     try_cnt: int = 3,
#     split_message: bool = False,
# ):
#     last_exc: Exception | None = None

#     # 첫 500자 메시지를 가져오고 나머지는 extra_blocks에 넣기
#     first_message = messages[0][:500] + "\n...\n\n\n 추가 내용 스레드에서 확인 ..."
#     full_message = messages[0]

#     if split_message:
#         message_lines = messages[0].split('\n')
#         first_message = message_lines[0] if message_lines else ""
#         full_message = '\n'.join(message_lines[1:]) if len(message_lines) > 1 else ""

#     logger.info(f"full_message: {full_message}")

#     for _ in range(try_cnt):
#         try:
#             async with httpx.AsyncClient() as session:
#                 data = {
#                     "level": level,
#                     "domain": Domain.HOTPARTNERS,
#                     "channel_id": channel_id,
#                     "title": title,
#                     "mentions": mentions,
#                     "messages": [first_message],
#                     "extra_blocks": extra_blocks,
#                     "send_new_thread": True,
#                     "filter_message": filter_message,
#                 }
#                 logger.info(
#                     f"""
#                         [슬랙 스레드 메세지 알람 request data]
#                         data: {data}
#                     """
#                 )
#                 response = await session.post(
#                     url=setting.AISTAGRAM_SLACK_URL,
#                     timeout=10,
#                     json=data
#                 )
#                 logger.info(
#                     f"""
#                         [슬랙 스레드 메세지 알람 response data]
#                         response: {response}
#                     """
#                 )

#                 thread_ts = None
#                 if response.status_code == HTTPStatus.OK:
#                     response_json = response.json()
#                     logger.debug(f"response_json: {response_json}")
#                     if isinstance(response_json.get('data'), dict):
#                         thread_ts = response_json['data'].get('ts', None)
#                     else:
#                         logger.debug(f"Unexpected data format: {response_json.get('data')}")
#                     break  # 성공적으로 보냈으면 루프를 빠져나감
#                 else:
#                     logger.info(f"response: {response}")
#                     response.raise_for_status()

#         except httpx.HTTPStatusError as e:
#             last_exc = e
#             logger.error(f"HTTPStatusError occurred: {str(e)}")
#             await asyncio.sleep(1)

#     # else:
#     #     # 모든 시도 실패 시 백업 메시지 전송
#     #     backup_send_result = await _backup_message_send(
#     #         title=title,
#     #         mentions=mentions,
#     #         message="\n".join(messages),
#     #     )
#     #     if backup_send_result:
#     #         return
#     #     raise Exception(f"Failed to send Slack message. ({last_exc})")

#     # 남은 메시지를 스레드로 전송
#     # if thread_ts:
#     if thread_ts and thread_ts != "No send message.":
#         logger.info(f"thread_ts: {thread_ts}")

#         # full_message_copied = full_message
#         while full_message:
#             remaining_message = full_message[:3000]
#             logger.info(f"remaining_message: {remaining_message}")
#             if not remaining_message:
#                 logger.info(f"no remaining_message -> break!!")
#                 break

#             try:
#                 extra_blocks=[
#                     MrkDwn(text=remaining_message).payload,
#                     Divider().payload,
#                 ]

#                 async with httpx.AsyncClient() as session:
#                     response = await session.post(
#                         url=setting.AISTAGRAM_SLACK_URL,
#                         timeout=10,
#                         json={
#                             "level": level,
#                             "domain": Domain.HOTPARTNERS,
#                             "channel_id": channel_id,
#                             "title": "",
#                             "mentions": [],
#                             "messages": [],
#                             "extra_blocks": extra_blocks,
#                             "send_new_thread": False,
#                             "filter_message": filter_message,
#                             # "thread_ts": thread_ts,
#                             "target_thread": thread_ts,
#                         }
#                     )
#                     if response.status_code == HTTPStatus.OK:
#                         full_message = full_message[3000:]
#                         break  # 성공적으로 보냈으면 루프를 빠져나감
#                     else:
#                         response.raise_for_status()
#             except httpx.HTTPStatusError as e:
#                 last_exc = e
#                 await asyncio.sleep(1)