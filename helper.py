import logging
import os
import sys
from dotenv import load_dotenv
from yambot import MessengerBot
from yambot.types import Update
from yandex_cloud_ml_sdk import YCloudML
from yandex_cloud_ml_sdk.search_indexes import StaticIndexChunkingStrategy, TextSearchIndexType
from yandex.cloud.ai.assistants.v1.threads.thread_pb2 import Thread
import pathlib



files_list = ['2121.md', 'vesta.md']
threads_list = {}

def local_path(path: str) -> pathlib.Path:
    return pathlib.Path(__file__).parent / path



def main():
    load_dotenv()
    print("Creating BOT")
    yb = MessengerBot(os.getenv('BOT_KEY'), log_level=logging.DEBUG)
    print("Starting SDK")
    sdk = YCloudML(folder_id=os.getenv('GPT_FOLDER'), auth=os.getenv('GPT_API_KEY'))

    print("Uploading files")
    files = []
    for path in files_list:
        file = sdk.files.upload(local_path(path), ttl_days=1, expiration_policy="static")
        files.append(file)


    operation = sdk.search_indexes.create_deferred(
        files,
        index_type=TextSearchIndexType(
            chunking_strategy=StaticIndexChunkingStrategy(
                max_chunk_size_tokens=700,
                chunk_overlap_tokens=300,
            )
        ),
    )
    print("Search index INIT")
    search_index = operation.wait()
    tool = sdk.tools.search_index(search_index)
    print("Assistant INIT")
    assistant = sdk.assistants.create("yandexgpt", tools=[tool])

    @yb.add_handler(command='/clear')
    def clear_context(update: Update):
        global threads_list
        thread: Thread = threads_list.get(f'{update.from_m.from_id}')
        if thread:
            threads_list.pop(f'{update.from_m.from_id}')
            thread.delete()

        yb.send_message(f'Context cleared for user {update.from_m.login}', update)


    @yb.add_handler(any=True)
    def process_any(update: Update):
        global threads_list
        thread: Thread = threads_list.get(f'{update.from_m.from_id}')

        if not thread:
            thread = sdk.threads.create()
            threads_list.update({f'{update.from_m.from_id}': thread})

        thread.write(update.text)
        run = assistant.run(thread)
        result = run.wait()

        print("Answer:", result.text)
        yb.send_message(result.text, update)

    try:
        yb.start_pooling()
    except KeyboardInterrupt:
        print("Closing")
        search_index.delete()
        assistant.delete()
        print("Bye")
        sys.exit(0)


if __name__ == "__main__":
    main()
