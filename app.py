# -*- coding: utf-8 -*-
"""
Time:     2023/4/28 14:56
Author:   Jyun
Version:  V 1.0
File:     app.py
Blog:     https://ctrlcv.blog.csdn.net
"""

import json
import os
# import re
import shutil
import time
from flask_httpauth import HTTPBasicAuth  # pip install flask_httpauth
from flask import Flask, Response, render_template, request, jsonify

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
auth = HTTPBasicAuth()

USER_LIST = [('root', 'root.123')]  # 用户列表

RELATIVE_PATH = r'./FILES'
BASE_DIR = os.path.abspath(RELATIVE_PATH)  # 用于浏览的文件夹

with open(os.path.abspath('./user.json'), 'r', encoding='utf8') as u:
    USER_LIST.extend(json.loads(u.read()))


class Tools:
    @staticmethod
    def size_convert(value):  # 文件大小 单位转换
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = 1024.0
        for i in range(len(units)):
            if (value / size) < 1:
                return "%.2f%s" % (value, units[i])
            value = value / size

    @staticmethod
    def getsize(path):
        if os.path.isfile(path):
            size_b = os.path.getsize(path)
            return Tools.size_convert(size_b)
        return '-'

    @staticmethod
    def getmtime(path):
        ctime = os.path.getmtime(path)
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ctime))

    @staticmethod
    def gettype(path):
        if os.path.isdir(path):
            return '文件夹'
        return os.path.splitext(path)[1].upper().strip('.') + '文件'


@app.route('/public/<path:index_path>')
def public_links(index_path=''):
    return 'ok'


@app.route('/')
@app.route('/<path:_index_path>')
@auth.login_required
def file_view(_index_path=''):
    index_path = os.path.join(*_index_path.split('/'))
    path = os.path.join(BASE_DIR, index_path)
    if os.path.isdir(path):  # 如果是文件夹
        dir_content = []
        for relative_path in os.listdir(path):
            final_path = os.path.join(path, relative_path)
            href = relative_path + '/' if os.path.isdir(final_path) else relative_path
            if href == '.chunk/': continue
            dir_content.append({
                'href': href,
                'type': Tools.gettype(final_path),
                'size': Tools.getsize(final_path),
                'modify_time': Tools.getmtime(final_path)
            })
        dir_content.sort(key=lambda x: x["modify_time"], reverse=True)
        index_of = ' > '.join(_index_path.strip('/').split('/'))
        return render_template('index.html', dir_content=dir_content, index_of=index_of)

    elif os.path.isfile(path):
        def send_chunk():  # 流式读取
            with open(path, 'rb') as target_file:
                while True:
                    chunk = target_file.read(20 * 1024 * 1024)  # 每次读取20M
                    if not chunk:
                        break
                    yield chunk

        response = Response(send_chunk(), content_type='application/octet-stream')
        response.headers["Content-Disposition"] = f'attachment'
        response.headers["Content-Length"] = str(os.path.getsize(path))
        return response

    # response = make_response(send_chunk())
    # response.headers['Content-Disposition'] = 'attachment; filename={}'.format(os.path.basename(path))
    # response.headers['Content-Type'] = 'application/octet-stream'
    # return response
    else:
        if request.args.get('opt') == 'newfolder':
            os.makedirs(path)
            return 'ok'
        return '404 Not Found'


@auth.verify_password
def verify_password(username, password):
    for user, pwd in USER_LIST:  # 简单直接 用户密码验证
        if username == user and password == pwd:
            return True
    return False


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']  # 获取分片数据
    chunk = int(request.form['chunk'])  # 获取分片序号
    total_chunks = int(request.form['totalChunks'])  # 获取分片总数
    filename = request.form['filename']  # 获取文件名
    filedir = request.form['dir'].strip('/')

    upload_folder = os.path.join(BASE_DIR, filedir)  # 指定上传文件的目录
    # upload_folder = '/path/to/upload/folder'  # 指定上传文件的目录
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    chunk_folder = os.path.join(upload_folder, '.chunk', filename)  # 指定当前文件的分片所在目录
    if not os.path.exists(chunk_folder):
        os.makedirs(chunk_folder)

    chunk_filename = os.path.join(chunk_folder, f'{chunk}.chunk')  # 构造当前分片的文件名
    file.save(chunk_filename)  # 将分片数据保存到文件中

    if chunk == total_chunks - 1:
        # 所有分片都已上传，开始合并文件
        with open(os.path.join(upload_folder, filename), 'wb') as output_file:
            for i in range(total_chunks):
                chunk_filename = os.path.join(chunk_folder, f'{i}.chunk')  # 获取每个分片的文件名
                with open(chunk_filename, 'rb') as input_file:
                    output_file.write(input_file.read())  # 将每个分片的数据写入到输出文件中

        # 合并完成后，删除分片所在目录
        shutil.rmtree(chunk_folder)

    return jsonify({'message': 'Chunk uploaded successfully'})


@app.route('/delete', methods=['POST'])
def delete():
    file = request.json['file']  # 获取文件名,也有可能是文件夹名
    filedir = request.json['dir'].strip('/')
    path = os.path.join(BASE_DIR, filedir, file)

    if not os.path.exists(path):
        return 'Unable to find the specified file or folder'
    elif os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)
    return 'ok'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8020, debug=True)

#  基于python Flask 的简易文件预览下载服务 含Flask基本身份验证