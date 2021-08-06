#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import aiohttp
import asyncio
import argparse
import progressbar
from base64 import b64encode
from time import clock

auth = {}
down_queue = None

async def dumpFile(src, dst, session):
    async with session as client:
        await dumpFileEx(src, dst, client)


async def dumpFileEx(src, dst, client):
    with open(src, 'rb') as fd:
        async with client.post(
            r'https://api.tinify.com/shrink', data=fd, headers=auth) as resp:
            if 201 != resp.status:
                print('FAIL:', src, resp.status)
                return
            else:
                src = resp.headers['Location']

    async with client.get(
        src, headers={'Content-Type': 'application/json'}) as resp:
        with open(dst, 'wb') as fd:
            async for data in resp.content.iter_chunked(1024):
                fd.write(data)
            print('DUMP:', dst)


async def walkFile(src, dst):
    for f in os.listdir(src):
        src_abs = os.path.join(src, f)
        dst_abs = os.path.join(dst, f)
        if os.path.isdir(src_abs):
            if not os.path.exists(dst_abs):
                os.mkdir(dst_abs)
            await walkFile(src_abs,dst_abs)
        elif f.endswith('.png') or f.endswith('.jpg'):
            await down_queue.put((src_abs, dst_abs))
            print('FIND:', f)


async def downWorker(id):
    async with aiohttp.ClientSession(
        skip_auto_headers=['User-Agent', 'Accept-Encoding']) as client:
        while True:
            abs = await down_queue.get()
            if len(abs) < 2:
                break
            start = clock()
            await dumpFileEx(abs[0], abs[1], client)
            print('TIME:', abs[0], abs[1], clock() - start)
            down_queue.task_done()

async def init(args,*,loop):
    global down_queue
    down_queue = asyncio.Queue(args.down_num)

    tasks = [loop.create_task(downWorker(i)) for i in range(args.down_num)]

    await walkFile(args.input, args.output)
    await down_queue.join()

def main(args):
    if not args.key:
        args.key = input("Enter API key:").strip()
    auth['Authorization'] = "Basic %s" % (
        b64encode(bytes("api:" + args.key, "ascii"))).decode("ascii")

    args.input = os.path.expanduser(args.input)
    if not os.path.exists(args.input):
        print("the input directory is not exist")
        return

    if not args.output:
        args.output = args.input
    else:
        args.output = os.path.expanduser(args.output)
        if not os.path.exists(args.output):
            os.mkdir(args.output)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(init(args,loop=loop))
    except KeyboardInterrupt as e:
        print(str(e))
    finally:
        for tk in asyncio.Task.all_tasks():
            tk.cancel()
        loop.run_forever()
        loop.close()


if '__main__' == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="the input directory",
        dest="input")
    parser.add_argument(
        "-o",
        "--output",
        help="the output directory. default is the same as the input",
        dest="output")
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=10,
        help="download the number of parallel. default is 2",
        dest="down_num")
    parser.add_argument(
        "-b",
        "--backup",
        help="backup original file. default off",
        dest="backup")
    parser.add_argument(
        "-k",
        "--key",
        default="ywesNc4pvgQZEZqT7WLsyQbIYYJ8uMrB",
        help="provide service app key",
        dest="key")
    args = parser.parse_args()
    main(args)
