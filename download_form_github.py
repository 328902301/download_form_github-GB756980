import re  # 导入正则表达式模块，用于模式匹配。
import os  # 导入操作系统相关功能模块（文件路径、目录）。
import json  # 导入 JSON 处理模块，用于读取和写入配置文件。
import py7zr  # 导入用于处理 7z 文件格式的库。
import zipfile  # 导入用于处理 zip 文件格式的库。
import urllib3  # 导入 HTTP 库，用于发起请求并提供额外功能。
import logging  # 导入日志模块，用于记录信息和错误。
import requests  # 导入库，简化 HTTP 请求的处理。
import fnmatch  # 导入文件名匹配模块，使用 Unix 风格的通配符。
import threading  # 导入线程模块，用于并发执行。
from tqdm import tqdm  # 导入进度条模块，用于在循环中显示进度。

# 定义配置文件和日志文件的名称
CONFIG_FILE = "config.json"
LOG_FILE = "download_log.txt"

# 定义 GitHub API 和 Raw URL 的全局变量
GITHUB_API_URL = "https://api.github.com"
GITHUB_RAW_URL = "https://raw.githubusercontent.com"


def setup_logging(log_file):
    """设置日志记录。"""
    if not os.path.exists(log_file):  # 如果日志文件不存在
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("")  # 初始化日志文件。

    # 定义控制台输出格式
    console_formatter = logging.Formatter('%(message)s')
    # 定义文件输出格式
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)  # 设置日志级别为 INFO。
    file_handler.setFormatter(file_formatter)  # 设置文件输出格式

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # 设置日志级别为 INFO。
    console_handler.setFormatter(console_formatter)  # 设置控制台输出格式

    # 配置日志记录
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

    # 禁用不安全请求的警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def read_or_update_json_file(file_name, data=None):
    """读取或更新 JSON 文件。"""
    try:
        if data is None:  # 如果没有提供数据，读取文件。
            with open(file_name, 'r', encoding='utf-8') as f:
                return json.load(f)  # 加载并返回 JSON 数据。
        else:  # 如果提供了数据，更新文件。
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)  # 将数据写入文件。
            logging.info(f"更新 JSON 文件: {file_name}")  # 记录更新操作。
    except (json.JSONDecodeError, IOError, Exception) as e:  # 处理文件错误。
        logging.error(f"操作 JSON 文件时发生错误: {e}")  # 记录错误信息。


def download_and_unzip(url, save_path, file_name, token=None):
    """从给定 URL 下载并解压文件。"""
    save_path = os.path.abspath(save_path)  # 获取保存路径的绝对路径。
    file_save_path = os.path.join(save_path, file_name)  # 构造文件的完整路径。
    older_version_file_path = os.path.join(save_path, f"【旧版本, 请手动删除】{file_name}")  # 旧版本文件路径。

    logging.info(f"准备下载文件：{file_name} 到 {save_path}")  # 记录下载准备信息。
    logging.info(f"下载链接为: {url}")  # 记录下载 URL。

    headers = {}
    if token:  # 如果提供了令牌，则将其添加到请求头中。
        headers['Authorization'] = f'token {token}'

    try:
        def is_file_locked(file_path):
            """检查文件是否被锁定（使用中）。"""
            try:
                with open(file_path, 'a'):  # 尝试以追加模式打开文件
                    return False  # 文件未被锁定
            except IOError:
                return True  # 文件被锁定

        if os.path.isfile(file_save_path):  # 检查文件是否已存在
            if is_file_locked(file_save_path):  # 检查文件是否被锁定
                logging.warning(f"{file_name} 已被占用, 尝试重命名为: 【旧版本, 请手动删除】{file_name}")
                try:
                    os.rename(file_save_path, older_version_file_path)  # 重命名旧文件
                    logging.info(f"现有文件已重命名为: {older_version_file_path}")
                except PermissionError:
                    logging.error(f"无法重命名文件: {file_name}, 文件可能正在被占用")
                    return False
                except Exception as e:
                    logging.error(f"重命名文件时发生错误: {e}")
                    return False
            else:
                logging.info(f"{file_name} 已存在, 但未被占用, 将直接下载并覆盖原文件")

        response = requests.get(url, headers=headers, stream=True, verify=False)  # 发起下载请求
        response.raise_for_status()  # 检查请求是否成功

        total_size = int(response.headers.get('content-length', 0))  # 获取文件大小
        os.makedirs(save_path, exist_ok=True)  # 创建保存路径
        with open(file_save_path, 'wb') as f, tqdm(
                desc=file_name,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                ncols=100,
                ascii=True) as bar:
            for chunk in response.iter_content(chunk_size=8192):  # 分块下载文件
                if chunk:
                    f.write(chunk)  # 写入文件
                    bar.update(len(chunk))  # 更新进度条

        logging.info(f"文件成功下载到: {file_save_path}")

        if file_name.endswith('.zip'):  # 如果是 zip 文件
            with zipfile.ZipFile(file_save_path, 'r') as zip_ref:
                zip_ref.extractall(save_path)  # 解压文件
            logging.info(f"已成功解压文件: {file_name}")
        elif file_name.endswith('.7z'):  # 如果是 7z 文件
            with py7zr.SevenZipFile(file_save_path, mode='r') as archive:
                archive.extractall(path=save_path)  # 解压文件
            logging.info(f"已成功解压文件: {file_name}")

    except requests.exceptions.RequestException as e:  # 处理请求异常
        logging.error(f"下载文件失败: {file_name}. 错误信息: {e}")
        return False
    except Exception as e:  # 处理其他异常
        logging.error(f"文件下载时发生错误: {e}")
        return False
    finally:
        if file_name.endswith('.zip') or file_name.endswith('.7z'):  # 删除压缩文件
            if os.path.exists(file_save_path):
                os.remove(file_save_path)  # 删除文件
                logging.info(f"已成功删除压缩文件: {file_save_path}")


def download_github_release(owner, repo, version, save_path, files=None, token=None):
    """下载最新的 GitHub Release 文件。"""
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/releases/latest"  # 构造 GitHub API URL
    headers = {'Authorization': f'token {token}'} if token else {}  # 设置请求头

    def update_version_in_config(owner, repo, latest_version):
        """更新 config.json 中指定项目的版本号。"""
        data = read_or_update_json_file(CONFIG_FILE) or {}  # 读取配置文件
        for project in data.get("release", []):  # 遍历项目
            if project.get("owner") == owner and project.get("repository") == repo:
                project["version"] = latest_version  # 更新版本号
        read_or_update_json_file(CONFIG_FILE, data)  # 写入配置文件
        logging.info(f"项目 {owner}/{repo} 的版本号已更新为: {latest_version}")

    try:
        response = requests.get(url, headers=headers)  # 发起请求
        response.raise_for_status()  # 检查请求是否成功

        release = response.json()  # 解析 JSON 数据
        latest_version = release.get('tag_name', 'unknown')  # 获取最新版本号

        # 检查版本号是否包含数字
        if re.search(r'\d', version) is None:  # 如果版本号没有数字
            logging.info(f"项目 {owner}/{repo} 的版本号不包含数字, 将优先下载最新 Release")
            assets = release.get('assets', [])  # 获取所有资产
            if assets:  # 如果有资产
                for asset in assets:
                    file_name = asset['name']  # 获取文件名
                    file_url = asset['browser_download_url']  # 获取下载链接
                    download_and_unzip(file_url, save_path, file_name, token)  # 下载并解压
            else:
                logging.info(f"项目 {owner}/{repo} 没有可用的 Release, 尝试下载最新的 Artifact")
                download_github_artifact(owner, repo, save_path, token=token)  # 下载最新的 Artifact

            # 更新 JSON 文件: config.json
            update_version_in_config(owner, repo, latest_version)

        elif version != latest_version:  # 如果版本不相同
            assets = release.get('assets', [])  # 获取所有资产
            files_to_download = [asset['name'] for asset in assets] if not files else files  # 计算需要下载的文件

            for asset in assets:  # 遍历资产
                file_name = asset['name']  # 获取文件名
                if any(fnmatch.fnmatch(file_name, pattern) for pattern in files_to_download):  # 匹配文件
                    file_url = asset['browser_download_url']  # 获取下载链接
                    download_and_unzip(file_url, save_path, file_name, token)  # 下载并解压

            # 更新 JSON 文件: config.json
            update_version_in_config(owner, repo, latest_version)

        else:
            logging.info(f"项目 {owner}/{repo} 本地版本为 {version}, 已是最新, 将跳过下载")

    except (requests.exceptions.RequestException, Exception) as e:  # 处理异常
        logging.error(f"处理 Release 时发生错误: {e}")


def download_github_artifact(owner, repo, save_path, token=None):
    """下载 GitHub 的 Artifact 文件。"""
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/actions/artifacts"  # 构造 GitHub API URL
    headers = {'Authorization': f'token {token}'} if token else {}  # 设置请求头

    try:
        response = requests.get(url, headers=headers)  # 发起请求
        response.raise_for_status()  # 检查请求是否成功

        artifacts = response.json().get('artifacts', [])  # 获取所有 Artifact
        if artifacts:  # 如果有 Artifact
            latest_artifact = artifacts[0]  # 获取最新的 Artifact
            artifact_url = latest_artifact['archive_download_url']  # 获取下载链接
            artifact_name = f"{latest_artifact['name']}.zip"  # 设置文件名

            download_and_unzip(artifact_url, save_path, artifact_name, token)  # 下载并解压
        else:
            logging.info("未找到 Artifact 文件。")
    except (requests.exceptions.RequestException, Exception) as e:  # 处理异常
        logging.error(f"处理 Github Artifact 时, 发生错误: {e}")


def download_github_file(owner, repo, save_path, folder=None, files=None, token=None):
    """从 GitHub Raw 下载文件，保留文件夹结构，并覆盖已存在的文件。"""
    base_url = f"{GITHUB_RAW_URL}/{owner}/{repo}/main/"  # 构造基础 URL

    def download_from_url(file_url, file_path):
        """从 URL 下载单个文件并覆盖已存在的文件。"""
        file_name = os.path.basename(file_path)  # 获取文件名
        file_dir = os.path.dirname(file_path)  # 获取文件目录

        if not os.path.exists(file_dir):  # 如果目录不存在
            os.makedirs(file_dir, exist_ok=True)  # 创建目录

        download_and_unzip(file_url, file_dir, file_name, token)  # 下载并解压

    def fetch_files_in_folder(folder_url):
        """获取指定文件夹中的所有文件，以便进行通配符匹配。"""
        response = requests.get(folder_url, headers={'Authorization': f'token {token}'} if token else {})  # 发起请求
        response.raise_for_status()  # 检查请求是否成功
        return response.json()  # 返回 JSON 数据

    def download_folder_contents(folder_url, folder_path, ignore_folder_structure):
        """递归下载文件夹中的所有文件和子文件夹。"""
        try:
            contents = fetch_files_in_folder(folder_url)  # 获取文件夹内容

            for item in contents:  # 遍历文件夹内容
                item_path = os.path.join(folder_path, item['name'])  # 构造文件路径
                if item['type'] == 'file':  # 如果是文件
                    file_url = item['download_url']  # 获取下载链接
                    if files:  # 如果指定了文件
                        for file_pattern in files:  # 遍历文件模式
                            if fnmatch.fnmatch(item['name'], file_pattern):  # 匹配文件名
                                download_from_url(file_url, item_path)  # 下载文件
                                break  # 找到后退出循环
                    else:
                        download_from_url(file_url, item_path)  # 下载文件
                elif item['type'] == 'dir':  # 如果是文件夹
                    subfolder_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents/{item['path']}"  # 构造子文件夹 URL
                    new_folder_path = item_path if not ignore_folder_structure else folder_path  # 决定新文件夹路径
                    download_folder_contents(subfolder_url, new_folder_path, ignore_folder_structure)  # 递归下载子文件夹内容
        except requests.exceptions.RequestException as e:  # 处理请求异常
            logging.error(f"下载 GitHub 文件夹 {folder_path} 时发生错误: {e}")

    try:
        if files:  # 如果指定了文件
            if folder:  # 如果指定了文件夹
                folder_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents{folder}"  # 构造文件夹 URL
                folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(
                    os.path.join(save_path, folder))  # 规范化文件夹路径
                os.makedirs(folder_path, exist_ok=True)  # 创建文件夹
                download_folder_contents(folder_url, folder_path, folder.startswith('/'))  # 下载文件夹内容
            else:
                folder_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents"  # 构造文件夹 URL
                full_save_path = os.path.normpath(save_path)  # 规范化保存路径
                os.makedirs(full_save_path, exist_ok=True)  # 创建保存路径
                download_folder_contents(folder_url, full_save_path, False)  # 下载文件夹内容
        else:  # 如果没有指定文件
            if folder is None:  # 如果没有指定文件夹
                folder_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents"  # 构造文件夹 URL
                full_save_path = os.path.normpath(save_path)  # 规范化保存路径
                os.makedirs(full_save_path, exist_ok=True)  # 创建保存路径
                download_folder_contents(folder_url, full_save_path, False)  # 下载文件夹内容
            else:  # 如果指定了文件夹
                folder_url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/contents{folder}"  # 构造文件夹 URL
                folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(
                    os.path.join(save_path, folder))  # 规范化文件夹路径
                os.makedirs(folder_path, exist_ok=True)  # 创建文件夹
                download_folder_contents(folder_url, folder_path, folder.startswith('/'))  # 下载文件夹内容

    except requests.exceptions.RequestException as e:  # 处理请求异常
        logging.error(f"下载 GitHub 文件时发生错误: {e}")


def modify_project_status(config, project_type):
    """显示项目列表，允许用户选择项目并切换其下载功能状态。"""
    projects = config.get(project_type, [])  # 获取指定项目类型的项目

    print(f"项目列表 - {project_type.capitalize()} 项目")  # 打印项目列表标题
    print("-" * 100)  # 打印分隔线
    for i, project in enumerate(projects):  # 遍历项目
        status_symbol = '√' if project['enabled'] == "true" else '×'  # 根据状态设置符号
        print(
            f"{i + 1}. [{status_symbol}] {'已启用' if project['enabled'] == 'true' else '未启用'}下载功能：{project['owner']}/{project['repository']}（{project.get('description', '')}）")

    print("-" * 100)  # 打印分隔线
    user_input = input(
        "请选择需要启用或禁用下载功能的项目序号（可用空格、英文逗号、中文逗号、分号或斜杠中的任一分隔符分隔多个项目序号）：")
    print("-" * 100)  # 打印分隔线

    selected_indices = [int(i.strip()) - 1 for i in re.split(r'[，,；;/\s]+', user_input) if
                        i.strip().isdigit()]  # 解析用户输入的项目序号

    invalid_indices = [i + 1 for i in selected_indices if i < 0 or i >= len(projects)]  # 检查无效的序号
    if invalid_indices:  # 如果有无效的序号
        print(f"以下序号无效：{', '.join(map(str, invalid_indices))}")  # 打印无效序号
        return config  # 返回原配置

    for index in selected_indices:  # 遍历选择的序号
        project = projects[index]  # 获取项目
        new_status = "false" if project["enabled"] == "true" else "true"  # 切换状态
        project["enabled"] = new_status  # 更新项目状态
        logging.info(
            f"项目 {project['owner']}/{project['repository']} 的下载已{'启用' if new_status == 'true' else '禁用'}。")  # 记录状态变化
        logging.info(f"{'-' * 100}")  # 打印分隔线

    read_or_update_json_file(CONFIG_FILE, config)  # 更新配置文件


def main():
    """主函数，执行下载任务或修改配置。"""
    setup_logging(LOG_FILE)  # 设置日志。
    logging.info(f"{'=' * 100}")  # 打印分隔线
    config = read_or_update_json_file(CONFIG_FILE)  # 读取配置文件
    logging.info(f"已读取配置文件: {CONFIG_FILE}")  # 记录读取操作
    logging.info(f"{'=' * 100}")  # 打印分隔线

    print("请选择操作，3秒内未输入则执行默认操作：")  # 提示用户选择操作
    print("-" * 100)  # 打印分隔线
    print("1. 更新 Github Release 、下载 Github 文件（默认操作）")  # 选项 1
    print("2. 修改“是否更新 Github Release”的标识")  # 选项 2
    print("3. 修改“是否下载 Github 文件”的标识")  # 选项 3
    print("-" * 100)  # 打印分隔线

    choice = None  # 初始化选择
    default_action_executed = False  # 标记是否执行默认操作

    timer = threading.Timer(3.0, lambda: (exec_default_action()))  # 设置 3 秒后执行默认操作的计时器

    def exec_default_action():
        """执行默认操作。"""
        print("=" * 100)  # 打印分隔线
        nonlocal default_action_executed  # 使用外部变量
        if not default_action_executed:  # 如果默认操作未执行
            default_action_executed = True  # 标记为已执行
            github_token = config.get("github_token")  # 从配置中获取 GitHub Token

            if github_token:  # 如果有 Token
                logging.info("已从 config.json 中加载 GitHub Token")  # 记录加载操作
                logging.info(f"{'=' * 100}")  # 打印分隔线
            else:  # 如果没有 Token
                logging.warning("未在 config.json 中配置 GitHub Token, 下载时将不携带 GitHub Token")  # 记录警告
                logging.info(f"{'=' * 100}")  # 打印分隔线

            logging.info("即将开始更新 Github 最新 Release")  # 记录更新操作
            logging.info(f"{'-' * 100}")  # 打印分隔线
            for project in config.get("release", []):  # 遍历所有 Release 项目
                if project.get("enabled") == "true":  # 检查项目是否启用
                    owner = project.get("owner")  # 获取项目拥有者
                    repo = project.get("repository")  # 获取项目仓库
                    version = project.get("version")  # 获取项目版本
                    save_path = os.path.expandvars(project.get("save_path"))  # 获取保存路径
                    files = project.get("files")  # 获取需要下载的文件
                    logging.info(f"即将处理项目: {owner}/{repo}")  # 记录处理项目
                    download_github_release(owner, repo, version, save_path, files, github_token)  # 下载 Release
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")  # 记录完成操作
                    logging.info(f"{'-' * 100}")  # 打印分隔线
                else:  # 如果未启用
                    logging.info(
                        f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")  # 记录跳过操作
                    logging.info(f"{'-' * 100}")  # 打印分隔线
            logging.info("Github 最新 Release 已更新完成")  # 记录完成操作
            logging.info(f"{'=' * 100}")  # 打印分隔线

            logging.info("即将开始下载 Github 文件")  # 记录下载操作
            logging.info(f"{'-' * 100}")  # 打印分隔线
            for project in config.get("file", []):  # 遍历所有文件项目
                if project.get("enabled") == "true":  # 检查项目是否启用
                    owner = project.get("owner")  # 获取项目拥有者
                    repo = project.get("repository")  # 获取项目仓库
                    save_path = os.path.expandvars(project.get("save_path"))  # 获取保存路径
                    folder = project.get("folder")  # 获取文件夹
                    files = project.get("files")  # 获取需要下载的文件

                    logging.info(f"即将处理项目: {owner}/{repo}")  # 记录处理项目
                    download_github_file(owner, repo, save_path, folder, files, github_token)  # 下载文件
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")  # 记录完成操作
                    logging.info(f"{'-' * 100}")  # 打印分隔线
                else:  # 如果未启用
                    logging.info(
                        f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")  # 记录跳过操作
                    logging.info(f"{'-' * 100}")  # 打印分隔线
            logging.info("Github 最新文件已下载完成")  # 记录完成操作
            logging.info(f"{'=' * 100}")  # 打印分隔线

    def get_user_input():
        """获取用户输入以选择操作。"""
        nonlocal choice  # 使用外部变量
        choice = input("请输入1、2 或 3 ，当输入其他时，将退出程序：\n")  # 获取用户输入
        timer.cancel()  # 取消计时器

    input_thread = threading.Thread(target=get_user_input)  # 创建线程获取用户输入
    input_thread.start()  # 启动线程

    timer.start()  # 启动计时器

    input_thread.join()  # 等待用户输入线程结束

    if choice == '1':  # 如果用户选择 1
        exec_default_action()  # 执行默认操作

    elif choice == '2':  # 如果用户选择 2
        print("=" * 100)  # 打印分隔线
        modify_project_status(config, "release")  # 修改 Release 项目的状态
        logging.info("=" * 100)  # 打印分隔线

    elif choice == '3':  # 如果用户选择 3
        print("=" * 100)  # 打印分隔线
        modify_project_status(config, "file")  # 修改文件项目的状态
        logging.info("=" * 100)  # 打印分隔线

    else:  # 如果用户输入无效
        logging.info("=" * 100)  # 打印分隔线
        logging.info("无效的选择，将退出程序")  # 记录无效选择
        logging.info("=" * 100)  # 打印分隔线


if __name__ == "__main__":  # 检查脚本是否直接运行。
    main()  # 执行主函数。
