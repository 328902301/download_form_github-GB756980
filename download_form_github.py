import re  # 引入正则表达式模块
import os  # 导入操作系统模块
import json  # 导入 JSON 模块
import py7zr  # 导入 7z 解压模块
import zipfile  # 导入 zip 解压模块
import urllib3  # 导入 urllib3 模块
import logging  # 导入日志模块
import requests  # 导入 HTTP 请求模块
import threading  # 导入线程模块
from tqdm import tqdm  # 导入进度条模块

# 设置日志配置
log_file = "download_log.txt"  # 指定日志文件名

# 确保日志文件以 UTF-8 编码创建
if not os.path.exists(log_file):  # 如果日志文件不存在
    with open(log_file, 'w', encoding='utf-8') as f:  # 创建新文件
        f.write("")  # 写入空内容

# 创建自定义控制台输出格式
console_formatter = logging.Formatter('%(message)s')  # 控制台输出格式（只保留消息）

# 配置文件日志
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')  # 文件输出格式（含时间戳）

# 配置文件日志处理器
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)  # 日志级别
file_handler.setFormatter(file_formatter)  # 设置格式

# 配置控制台日志处理器
console_handler = logging.StreamHandler()  # 创建控制台日志处理
console_handler.setLevel(logging.INFO)  # 设置控制台日志级别
console_handler.setFormatter(console_formatter)  # 设置格式

# 配置日志记录器
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])  # 添加处理器

# 禁用不安全请求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = "config.json"  # 配置文件名

def read_or_update_json_file(file_name, data=None):
    """读取或更新 JSON 文件。"""
    try:
        if data is None:  # 如果没有传入数据，读取文件
            with open(file_name, 'r', encoding='utf-8') as f:
                return json.load(f)  # 返回 JSON 内容
        else:  # 否则，更新文件
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)  # 写入 JSON 数据
            logging.info(f"更新 JSON 文件: {file_name}")  # 记录日志
    except (json.JSONDecodeError, IOError, Exception) as e:  # 异常处理
        logging.error(f"操作 JSON 文件时发生错误: {e}")  # 记录错误日志

def download_and_unzip(url, save_path, file_name, token=None):
    """
    下载并解压文件。

    :param url: 文件的下载链接
    :param save_path: 文件保存路径
    :param file_name: 文件名称
    :param token: GitHub 访问令牌（可选）
    """
    file_save_path = os.path.join(save_path, file_name)  # 完整文件保存路径
    older_version_file_path = os.path.join(save_path, f"【旧版本, 请手动删除】{file_name}")  # 旧版本文件路径

    logging.info(f"准备下载文件：{file_name} 到 {save_path}")  # 记录下载准备信息
    logging.info(f"下载链接为: {url}")  # 记录下载链接

    headers = {}  # 请求头
    if token:  # 如果提供了 token
        headers['Authorization'] = f'token {token}'  # 添加授权头

    try:
        def is_file_locked(file_path):
            """
            检查文件是否被锁定。

            :param file_path: 文件路径
            :return: 如果文件被锁定，则返回 True，否则返回 False
            """
            try:
                with open(file_path, 'a'):  # 尝试以附加模式打开文件
                    return False  # 文件未被锁定
            except IOError:  # 捕获 IOError
                return True  # 文件被锁定

        if os.path.isfile(file_save_path):  # 如果文件已存在
            if is_file_locked(file_save_path):  # 检查文件是否被锁定
                logging.warning(f"{file_name} 已被占用, 尝试重命名为: 【旧版本, 请手动删除】{file_name}")  # 记录警告日志
                try:
                    os.rename(file_save_path, older_version_file_path)  # 重命名文件
                    logging.info(f"现有文件已重命名为: {older_version_file_path}")  # 记录重命名成功日志
                except PermissionError:  # 捕获权限错误
                    logging.error(f"无法重命名文件: {file_name}, 文件可能正在被占用")  # 记录错误日志
                    return False
                except Exception as e:  # 捕获其他异常
                    logging.error(f"重命名文件时发生错误: {e}")  # 记录错误日志
                    return False
            else:
                logging.info(f"{file_name} 已存在, 但未被占用, 将直接下载并覆盖原文件")  # 记录信息

        # 下载文件
        response = requests.get(url, headers=headers, stream=True, verify=False)  # 发送 GET 请求
        response.raise_for_status()  # 检查请求是否成功

        total_size = int(response.headers.get('content-length', 0))  # 获取文件总大小
        os.makedirs(save_path, exist_ok=True)  # 确保保存路径存在
        with open(file_save_path, 'wb') as f, tqdm(
                desc=file_name,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                ncols=100,
                ascii=True) as bar:  # 显示下载进度条
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # 如果有数据块
                    f.write(chunk)  # 写入文件
                    bar.update(len(chunk))  # 更新进度条

        logging.info(f"文件成功下载到: {file_save_path}")  # 记录下载成功日志

        # 解压文件
        if file_name.endswith('.zip'):  # 如果是 ZIP 文件
            with zipfile.ZipFile(file_save_path, 'r') as zip_ref:
                zip_ref.extractall(save_path)  # 解压到指定路径
            logging.info(f"已成功解压文件: {file_name}")  # 记录解压成功日志
        elif file_name.endswith('.7z'):  # 如果是 7z 文件
            with py7zr.SevenZipFile(file_save_path, mode='r') as archive:
                archive.extractall(path=save_path)  # 解压到指定路径
            logging.info(f"已成功解压文件: {file_name}")  # 记录解压成功日志

    except requests.exceptions.RequestException as e:  # 捕获请求异常
        logging.error(f"下载文件失败: {file_name}. 错误信息: {e}")  # 记录错误日志
        return False
    except Exception as e:  # 捕获其他异常
        logging.error(f"文件下载时发生错误: {e}")  # 记录错误日志
        return False

    finally:
        # 删除压缩文件
        if file_name.endswith('.zip') or file_name.endswith('.7z'):  # 如果是压缩文件
            if os.path.exists(file_save_path):  # 检查文件是否存在
                os.remove(file_save_path)  # 删除压缩文件
                logging.info(f"已成功删除压缩文件: {file_save_path}")  # 记录删除日志

def download_github_release(owner, repo, version, save_path, files=None, token=None):
    """
    下载 GitHub Release 的文件。

    :param owner: GitHub 仓库所有者
    :param repo: GitHub 仓库名称
    :param version: 版本号或 "CI" 表示最新版本
    :param save_path: 文件保存路径
    :param files: 要下载的文件列表（可选）
    :param token: GitHub 访问令牌（可选）
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"  # 获取最新发布信息的 URL
    headers = {'Authorization': f'token {token}'} if token else {}  # 设置请求头

    try:
        response = requests.get(url, headers=headers)  # 发送 GET 请求获取发布信息
        response.raise_for_status()  # 检查请求是否成功

        release = response.json()  # 获取 JSON 数据
        latest_version = release.get('tag_name', 'unknown')  # 获取最新版本号

        if version == "CI":  # 如果版本为 CI
            logging.info(f"项目 {owner}/{repo} 版本号为 CI, 将优先下载最新 Release")  # 记录信息
            assets = release.get('assets', [])  # 获取发布资产
            if assets:  # 如果有资产
                for asset in assets:
                    file_name = asset['name']  # 获取文件名
                    file_url = asset['browser_download_url']  # 获取下载链接
                    download_and_unzip(file_url, save_path, file_name, token)  # 下载并解压文件
            else:
                # 如果没有 release 资产, 下载最新 artifact
                logging.info(f"项目 {owner}/{repo} 没有可用的 Release, 尝试下载最新的 Artifact")  # 记录信息
                download_github_artifact(owner, repo, save_path, token=token)  # 下载最新 artifact
        elif version != latest_version:  # 如果版本不一致
            assets = release.get('assets', [])  # 获取发布资产
            files_to_download = [asset['name'] for asset in assets] if not files else files  # 确定需要下载的文件

            for asset in assets:  # 遍历资产
                file_name = asset['name']  # 获取文件名
                if file_name in files_to_download:  # 如果文件名在需要下载的列表中
                    file_url = asset['browser_download_url']  # 获取下载链接
                    download_and_unzip(file_url, save_path, file_name, token)  # 下载并解压

            # 更新版本信息
            data = read_or_update_json_file(CONFIG_FILE) or {}  # 读取当前配置
            for project in data.get("release", []):  # 遍历项目
                if project.get("owner") == owner and project.get("repository") == repo:  # 检查项目
                    project["version"] = latest_version  # 更新版本号
            read_or_update_json_file(CONFIG_FILE, data)  # 保存更新后的配置
        else:
            logging.info(f"项目 {owner}/{repo} 本地版本为 {version}, 已是最新, 将跳过下载")  # 记录信息
    except (requests.exceptions.RequestException, Exception) as e:  # 捕获异常
        logging.error(f"处理 Release 时发生错误: {e}")  # 记录错误日志

def download_github_artifact(owner, repo, save_path, token=None):
    """
    下载 GitHub 的 artifact 文件。

    :param owner: GitHub 仓库所有者
    :param repo: GitHub 仓库名称
    :param save_path: 文件保存路径
    :param token: GitHub 访问令牌（可选）
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts"  # 获取 artifact 列表的 URL
    headers = {'Authorization': f'token {token}'} if token else {}  # 设置请求头

    try:
        response = requests.get(url, headers=headers)  # 发送 GET 请求获取 artifact 列表
        response.raise_for_status()  # 检查请求是否成功

        artifacts = response.json().get('artifacts', [])  # 获取 artifact 列表
        if artifacts:  # 如果有 artifacts
            latest_artifact = artifacts[0]  # 假设第一个 artifact 是最新的
            artifact_url = latest_artifact['archive_download_url']  # 获取下载链接
            artifact_name = f"{latest_artifact['name']}.zip"  # 构造文件名

            download_and_unzip(artifact_url, save_path, artifact_name, token)  # 下载并解压 artifact
        else:
            logging.info("未找到 Artifact 文件。")  # 记录信息
    except (requests.exceptions.RequestException, Exception) as e:  # 捕获异常
        logging.error(f"处理 Github Artifact 时, 发生错误: {e}")  # 记录错误日志

def download_github_file(owner, repo, save_path, folder=None, files=None, token=None):
    """
    从 GitHub Raw 下载文件, 保留文件夹结构，并覆盖已存在的文件。

    :param owner: GitHub 仓库所有者
    :param repo: GitHub 仓库名称
    :param save_path: 文件保存路径
    :param folder: 文件夹路径（可选）
    :param files: 要下载的文件列表（可选）
    :param token: GitHub 访问令牌（可选）
    """
    base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/"  # 基础 URL

    def download_from_url(file_url, file_path):
        """
        下载单个文件并覆盖已存在的文件。

        :param file_url: 文件的下载链接
        :param file_path: 文件保存路径
        """
        file_name = os.path.basename(file_path)  # 获取文件名
        file_dir = os.path.dirname(file_path)  # 获取文件目录

        # 确保目录存在
        if not os.path.exists(file_dir):  # 如果目录不存在
            os.makedirs(file_dir, exist_ok=True)  # 创建目录

        # 下载文件并覆盖
        download_and_unzip(file_url, file_dir, file_name, token)  # 下载并解压文件

    def download_folder_contents(folder_url, folder_path):
        """
        递归下载文件夹中的所有文件和子文件夹。

        :param folder_url: 文件夹的 URL
        :param folder_path: 文件夹保存路径
        """
        try:
            response = requests.get(folder_url, headers={'Authorization': f'token {token}'} if token else {})  # 发送请求
            response.raise_for_status()  # 检查请求是否成功
            contents = response.json()  # 获取 JSON 内容

            for item in contents:  # 遍历内容
                item_path = os.path.join(folder_path, item['name'])  # 构造路径
                if item['type'] == 'file':  # 如果是文件
                    file_url = item['download_url']  # 获取下载链接
                    download_from_url(file_url, item_path)  # 下载文件
                elif item['type'] == 'dir':  # 如果是文件夹
                    subfolder_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}"  # 获取子文件夹 URL
                    download_folder_contents(subfolder_url, item_path)  # 递归下载
        except requests.exceptions.RequestException as e:  # 捕获请求异常
            logging.error(f"下载 GitHub 文件夹 {folder_path} 时发生错误: {e}")  # 记录错误日志

    try:
        if files:  # 如果需要下载指定文件
            if folder is None:  # folder 为空，下载根目录的 files 文件
                for file_name in files:
                    file_url = f"{base_url}{file_name}"  # 构造文件 URL
                    file_path = os.path.normpath(os.path.join(save_path, file_name))  # 构造文件保存路径
                    download_from_url(file_url, file_path)  # 下载文件
            else:  # folder 不为空
                for file_name in files:
                    # 确保 folder 和 file_name 之间没有多余的斜杠
                    file_url = f"{base_url}{folder.rstrip('/')}/{file_name}"  # 构造文件 URL
                    file_path = os.path.normpath(os.path.join(save_path, file_name))  # 构造文件保存路径
                    download_from_url(file_url, file_path)  # 下载文件

        else:  # 如果没有指定文件
            if folder is None:  # folder 为空，下载根目录的所有文件
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents"  # 获取根目录内容 URL
                full_save_path = os.path.normpath(save_path)  # 保持 save_path 不变
                os.makedirs(full_save_path, exist_ok=True)  # 创建文件夹
                download_folder_contents(folder_url, full_save_path)  # 递归下载
            else:  # folder 不为空
                # 处理 folder 为空的情况
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents{folder}"  # 获取文件夹内容 URL
                # 如果 folder 以 '/' 开头，则不在 save_path 中体现当前 folder 结构
                if folder.startswith('/'):
                    folder_path = os.path.normpath(save_path)  # 保持 save_path 不变
                else:  # 如果 folder 不以 '/' 开头
                    folder_path = os.path.normpath(os.path.join(save_path, folder))  # 使用 folder 更新保存路径

                os.makedirs(folder_path, exist_ok=True)  # 创建文件夹
                download_folder_contents(folder_url, folder_path)  # 递归下载

    except requests.exceptions.RequestException as e:  # 捕获请求异常
        logging.error(f"下载 GitHub 文件时发生错误: {e}")  # 记录错误日志

def modify_project_status(config, project_type):
    """
    显示项目列表，允许用户选择项目并切换其下载功能状态。

    :param config: 当前的配置信息
    :param project_type: 要修改的项目类型（"release" 或 "file"）
    :return: 修改后的配置
    """
    projects = config.get(project_type, [])  # 获取项目列表

    # 显示项目列表
    print(f"项目列表 - {project_type.capitalize()} 项目")
    print("-" * 100)  # 分隔线
    for i, project in enumerate(projects):
        status_symbol = '√' if project['enabled'] == 'true' else '×'  # 状态符号
        print(f"{i + 1}. [{status_symbol}] {'已启用' if project['enabled'] == 'true' else '未启用'}下载功能：{project['owner']}/{project['repository']}（{project.get('description', '')}）")

    print("-" * 100)  # 分隔线
    user_input = input("请选择需要启用或禁用下载功能的项目序号（可用空格、英文逗号、中文逗号、分号或斜杠中的任一分隔符分隔多个项目序号）：")  # 用户输入
    print("-" * 100)  # 分隔线

    # 使用正则表达式分割输入，支持多种分隔符
    selected_indices = [int(i.strip()) - 1 for i in re.split(r'[，,；;/\s]+', user_input) if i.strip().isdigit()]

    # 检查输入的序号是否有效
    invalid_indices = [i + 1 for i in selected_indices if i < 0 or i >= len(projects)]  # 找到无效序号
    if invalid_indices:  # 如果有无效序号
        print(f"以下序号无效：{', '.join(map(str, invalid_indices))}")  # 提示无效序号
        return config  # 返回当前配置

    # 切换项目的状态
    for index in selected_indices:
        project = projects[index]  # 获取项目
        new_status = "false" if project["enabled"] == "true" else "true"  # 切换状态
        project["enabled"] = new_status  # 更新状态
        logging.info(f"项目 {project['owner']}/{project['repository']} 的下载已{'启用' if new_status == 'true' else '禁用'}。")  # 提示用户
        logging.info(f"{'-' * 100}")  # 分隔线

    # 保存更新后的配置
    read_or_update_json_file(CONFIG_FILE, config)  # 保存配置

def main():
    """主函数, 执行下载任务或修改配置。"""
    logging.info(f"{'=' * 100}")  # 分隔线
    config = read_or_update_json_file(CONFIG_FILE)  # 读取配置文件
    logging.info(f"已读取配置文件: {CONFIG_FILE}")  # 记录读取日志
    logging.info(f"{'=' * 100}")  # 分隔线

    print("请选择操作，3秒内未输入则执行默认操作：")
    print("-" * 100)  # 分隔线
    print("1. 更新  Github Release 、下载 Github 文件（默认操作）")  # 选项 1
    print("2. 修改“是否更新  Github Release”的标识")  # 选项 2
    print("3. 修改“是否下载 Github 文件”的标识")  # 选项 3
    print("-" * 100)  # 分隔线

    choice = None  # 初始化选择变量
    default_action_executed = False  # 标志位，表示默认操作是否已执行

    timer = threading.Timer(3.0, lambda: (exec_default_action()))  # 创建一个3秒的定时器

    def exec_default_action():
        print("=" * 100)  # 分隔线
        nonlocal default_action_executed
        if not default_action_executed:  # 如果默认操作未执行
            default_action_executed = True  # 设置标志位
            github_token = config.get("github_token")  # 获取 GitHub Token

            if github_token:  # 如果提供了 Token
                logging.info("已从 config.json 中加载 GitHub Token")  # 记录信息
                logging.info(f"{'=' * 100}")  # 分隔线
            else:  # 如果没有提供 Token
                logging.warning("未在 config.json 中配置 GitHub Token, 下载时将不携带 GitHub Token")  # 记录警告
                logging.info(f"{'=' * 100}")  # 分隔线

            logging.info("即将开始更新 Github 最新 Release")  # 记录信息
            logging.info(f"{'-' * 100}")  # 分隔线
            for project in config.get("release", []):  # 遍历 Release 项目
                if project.get("enabled") == "true":  # 如果启用下载功能
                    owner = project.get("owner")  # 获取所有者
                    repo = project.get("repository")  # 获取仓库名称
                    version = project.get("version")  # 获取版本
                    save_path = os.path.expandvars(project.get("save_path"))  # 获取保存路径
                    files = project.get("files")  # 获取文件列表
                    logging.info(f"即将处理项目: {owner}/{repo}")  # 记录信息
                    download_github_release(owner, repo, version, save_path, files, github_token)  # 下载 Release
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")  # 记录信息
                    logging.info(f"{'-' * 100}")  # 分隔线
                else:
                    logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")  # 记录信息
                    logging.info(f"{'-' * 100}")  # 分隔线
            logging.info("Github 最新 Release 已更新完成")  # 记录信息
            logging.info(f"{'=' * 100}")  # 分隔线

            logging.info("即将开始下载 Github 文件")  # 记录信息
            for project in config.get("file", []):  # 遍历文件项目
                if project.get("enabled") == "true":  # 如果启用下载功能
                    owner = project.get("owner")  # 获取所有者
                    repo = project.get("repository")  # 获取仓库名称
                    save_path = os.path.expandvars(project.get("save_path"))  # 获取保存路径
                    folder = project.get("folder")  # 获取文件夹
                    files = project.get("files")  # 获取文件列表

                    logging.info(f"即将处理项目: {owner}/{repo}")  # 记录信息
                    download_github_file(owner, repo, save_path, folder, files, github_token)  # 下载文件
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")  # 记录信息
                    logging.info(f"{'-' * 100}")  # 分隔线
                else:
                    logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")  # 记录信息
                    logging.info(f"{'-' * 100}")  # 分隔线
            logging.info("Github 最新文件已下载完成")  # 记录信息
            logging.info(f"{'=' * 100}")  # 分隔线

    def get_user_input():
        nonlocal choice  # 使用外部作用域的变量
        choice = input("请输入1、2 或 3 ，当输入其他时，将退出程序：\n")  # 用户输入选择
        timer.cancel()  # 用户输入后取消定时器

    # 启动获取用户输入的线程
    input_thread = threading.Thread(target=get_user_input)
    input_thread.start()

    # 启动计时器
    timer.start()

    # 等待用户输入线程结束
    input_thread.join()

    if choice == '1':  # 如果选择执行所有项目
        exec_default_action()  # 执行默认操作

    elif choice == '2':  # 如果选择修改更新 Release
        print("=" * 100)  # 分隔线
        modify_project_status(config, "release")  # 只显示 Release 项目
        logging.info("=" * 100)  # 分隔线

    elif choice == '3':  # 如果选择修改下载文件
        print("=" * 100)  # 分隔线
        modify_project_status(config, "file")  # 只显示 File 项目
        logging.info("=" * 100)  # 分隔线

    else:  # 如果输入无效
        logging.info("=" * 100)  # 分隔线
        logging.info("无效的选择，将退出程序")  # 提示用户
        logging.info("=" * 100)  # 分隔线

if __name__ == "__main__":  # 如果是主模块
    main()  # 执行主函数