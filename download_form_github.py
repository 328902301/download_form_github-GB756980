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

CONFIG_FILE = "config.json"


def setup_logging(log_file="download_log.txt"):
    """设置日志记录。"""
    if not os.path.exists(log_file):
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("")  # 初始化日志文件。

    console_formatter = logging.Formatter('%(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)  # 设置日志级别为 INFO。
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # 设置日志级别为 INFO。
    console_handler.setFormatter(console_formatter)

    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

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
                with open(file_path, 'a'):
                    return False
            except IOError:
                return True

        if os.path.isfile(file_save_path):
            if is_file_locked(file_save_path):
                logging.warning(f"{file_name} 已被占用, 尝试重命名为: 【旧版本, 请手动删除】{file_name}")
                try:
                    os.rename(file_save_path, older_version_file_path)
                    logging.info(f"现有文件已重命名为: {older_version_file_path}")
                except PermissionError:
                    logging.error(f"无法重命名文件: {file_name}, 文件可能正在被占用")
                    return False
                except Exception as e:
                    logging.error(f"重命名文件时发生错误: {e}")
                    return False
            else:
                logging.info(f"{file_name} 已存在, 但未被占用, 将直接下载并覆盖原文件")

        response = requests.get(url, headers=headers, stream=True, verify=False)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        os.makedirs(save_path, exist_ok=True)
        with open(file_save_path, 'wb') as f, tqdm(
                desc=file_name,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                ncols=100,
                ascii=True) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))

        logging.info(f"文件成功下载到: {file_save_path}")

        if file_name.endswith('.zip'):
            with zipfile.ZipFile(file_save_path, 'r') as zip_ref:
                zip_ref.extractall(save_path)
            logging.info(f"已成功解压文件: {file_name}")
        elif file_name.endswith('.7z'):
            with py7zr.SevenZipFile(file_save_path, mode='r') as archive:
                archive.extractall(path=save_path)
            logging.info(f"已成功解压文件: {file_name}")

    except requests.exceptions.RequestException as e:
        logging.error(f"下载文件失败: {file_name}. 错误信息: {e}")
        return False
    except Exception as e:
        logging.error(f"文件下载时发生错误: {e}")
        return False
    finally:
        if file_name.endswith('.zip') or file_name.endswith('.7z'):
            if os.path.exists(file_save_path):
                os.remove(file_save_path)
                logging.info(f"已成功删除压缩文件: {file_save_path}")


def download_github_release(owner, repo, version, save_path, files=None, token=None):
    """下载最新的 GitHub Release 文件。"""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {'Authorization': f'token {token}'} if token else {}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        release = response.json()
        latest_version = release.get('tag_name', 'unknown')

        if version == "CI":
            logging.info(f"项目 {owner}/{repo} 版本号为 CI, 将优先下载最新 Release")
            assets = release.get('assets', [])
            if assets:
                for asset in assets:
                    file_name = asset['name']
                    file_url = asset['browser_download_url']
                    download_and_unzip(file_url, save_path, file_name, token)
            else:
                logging.info(f"项目 {owner}/{repo} 没有可用的 Release, 尝试下载最新的 Artifact")
                download_github_artifact(owner, repo, save_path, token=token)
        elif version != latest_version:
            assets = release.get('assets', [])
            files_to_download = [asset['name'] for asset in assets] if not files else files

            for asset in assets:
                file_name = asset['name']
                if any(fnmatch.fnmatch(file_name, pattern) for pattern in files_to_download):
                    file_url = asset['browser_download_url']
                    download_and_unzip(file_url, save_path, file_name, token)

            data = read_or_update_json_file(CONFIG_FILE) or {}
            for project in data.get("release", []):
                if project.get("owner") == owner and project.get("repository") == repo:
                    project["version"] = latest_version
            read_or_update_json_file(CONFIG_FILE, data)
        else:
            logging.info(f"项目 {owner}/{repo} 本地版本为 {version}, 已是最新, 将跳过下载")
    except (requests.exceptions.RequestException, Exception) as e:
        logging.error(f"处理 Release 时发生错误: {e}")


def download_github_artifact(owner, repo, save_path, token=None):
    """下载 GitHub 的 Artifact 文件。"""
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts"
    headers = {'Authorization': f'token {token}'} if token else {}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        artifacts = response.json().get('artifacts', [])
        if artifacts:
            latest_artifact = artifacts[0]
            artifact_url = latest_artifact['archive_download_url']
            artifact_name = f"{latest_artifact['name']}.zip"

            download_and_unzip(artifact_url, save_path, artifact_name, token)
        else:
            logging.info("未找到 Artifact 文件。")
    except (requests.exceptions.RequestException, Exception) as e:
        logging.error(f"处理 Github Artifact 时, 发生错误: {e}")


def download_github_file(owner, repo, save_path, folder=None, files=None, token=None):
    """从 GitHub Raw 下载文件，保留文件夹结构，并覆盖已存在的文件。"""
    base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/"

    def download_from_url(file_url, file_path):
        """从 URL 下载单个文件并覆盖已存在的文件。"""
        file_name = os.path.basename(file_path)
        file_dir = os.path.dirname(file_path)

        if not os.path.exists(file_dir):
            os.makedirs(file_dir, exist_ok=True)

        download_and_unzip(file_url, file_dir, file_name, token)

    def fetch_files_in_folder(folder_url):
        """获取指定文件夹中的所有文件，以便进行通配符匹配。"""
        response = requests.get(folder_url, headers={'Authorization': f'token {token}'} if token else {})
        response.raise_for_status()
        return response.json()

    def download_folder_contents(folder_url, folder_path, ignore_folder_structure):
        """递归下载文件夹中的所有文件和子文件夹。"""
        try:
            contents = fetch_files_in_folder(folder_url)

            for item in contents:
                item_path = os.path.join(folder_path, item['name'])
                if item['type'] == 'file':
                    file_url = item['download_url']
                    if files:
                        for file_pattern in files:
                            if fnmatch.fnmatch(item['name'], file_pattern):
                                download_from_url(file_url, item_path)
                                break
                    else:
                        download_from_url(file_url, item_path)
                elif item['type'] == 'dir':
                    subfolder_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}"
                    new_folder_path = item_path if not ignore_folder_structure else folder_path
                    download_folder_contents(subfolder_url, new_folder_path, ignore_folder_structure)
        except requests.exceptions.RequestException as e:
            logging.error(f"下载 GitHub 文件夹 {folder_path} 时发生错误: {e}")

    try:
        if files:
            if folder:
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents{folder}"
                folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(
                    os.path.join(save_path, folder))
                os.makedirs(folder_path, exist_ok=True)
                download_folder_contents(folder_url, folder_path, folder.startswith('/'))
            else:
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
                full_save_path = os.path.normpath(save_path)
                os.makedirs(full_save_path, exist_ok=True)
                download_folder_contents(folder_url, full_save_path, False)
        else:
            if folder is None:
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
                full_save_path = os.path.normpath(save_path)
                os.makedirs(full_save_path, exist_ok=True)
                download_folder_contents(folder_url, full_save_path, False)
            else:
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents{folder}"
                folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(
                    os.path.join(save_path, folder))
                os.makedirs(folder_path, exist_ok=True)
                download_folder_contents(folder_url, folder_path, folder.startswith('/'))

    except requests.exceptions.RequestException as e:
        logging.error(f"下载 GitHub 文件时发生错误: {e}")


def modify_project_status(config, project_type):
    """显示项目列表，允许用户选择项目并切换其下载功能状态。"""
    projects = config.get(project_type, [])

    print(f"项目列表 - {project_type.capitalize()} 项目")
    print("-" * 100)
    for i, project in enumerate(projects):
        status_symbol = '√' if project['enabled'] == "true" else '×'
        print(
            f"{i + 1}. [{status_symbol}] {'已启用' if project['enabled'] == 'true' else '未启用'}下载功能：{project['owner']}/{project['repository']}（{project.get('description', '')}）")

    print("-" * 100)
    user_input = input(
        "请选择需要启用或禁用下载功能的项目序号（可用空格、英文逗号、中文逗号、分号或斜杠中的任一分隔符分隔多个项目序号）：")
    print("-" * 100)

    selected_indices = [int(i.strip()) - 1 for i in re.split(r'[，,；;/\s]+', user_input) if i.strip().isdigit()]

    invalid_indices = [i + 1 for i in selected_indices if i < 0 or i >= len(projects)]
    if invalid_indices:
        print(f"以下序号无效：{', '.join(map(str, invalid_indices))}")
        return config

    for index in selected_indices:
        project = projects[index]
        new_status = "false" if project["enabled"] == "true" else "true"
        project["enabled"] = new_status
        logging.info(
            f"项目 {project['owner']}/{project['repository']} 的下载已{'启用' if new_status == 'true' else '禁用'}。")
        logging.info(f"{'-' * 100}")

    read_or_update_json_file(CONFIG_FILE, config)


def main():
    """主函数，执行下载任务或修改配置。"""
    setup_logging()  # 设置日志。
    logging.info(f"{'=' * 100}")
    config = read_or_update_json_file(CONFIG_FILE)
    logging.info(f"已读取配置文件: {CONFIG_FILE}")
    logging.info(f"{'=' * 100}")

    print("请选择操作，3秒内未输入则执行默认操作：")
    print("-" * 100)
    print("1. 更新 Github Release 、下载 Github 文件（默认操作）")
    print("2. 修改“是否更新 Github Release”的标识")
    print("3. 修改“是否下载 Github 文件”的标识")
    print("-" * 100)

    choice = None
    default_action_executed = False

    timer = threading.Timer(3.0, lambda: (exec_default_action()))

    def exec_default_action():
        """执行默认操作。"""
        print("=" * 100)
        nonlocal default_action_executed
        if not default_action_executed:
            default_action_executed = True
            github_token = config.get("github_token")

            if github_token:
                logging.info("已从 config.json 中加载 GitHub Token")
                logging.info(f"{'=' * 100}")
            else:
                logging.warning("未在 config.json 中配置 GitHub Token, 下载时将不携带 GitHub Token")
                logging.info(f"{'=' * 100}")

            logging.info("即将开始更新 Github 最新 Release")
            logging.info(f"{'-' * 100}")
            for project in config.get("release", []):
                if project.get("enabled") == "true":
                    owner = project.get("owner")
                    repo = project.get("repository")
                    version = project.get("version")
                    save_path = os.path.expandvars(project.get("save_path"))
                    files = project.get("files")
                    logging.info(f"即将处理项目: {owner}/{repo}")
                    download_github_release(owner, repo, version, save_path, files, github_token)
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")
                    logging.info(f"{'-' * 100}")
                else:
                    logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")
                    logging.info(f"{'-' * 100}")
            logging.info("Github 最新 Release 已更新完成")
            logging.info(f"{'=' * 100}")

            logging.info("即将开始下载 Github 文件")
            logging.info(f"{'-' * 100}")
            for project in config.get("file", []):
                if project.get("enabled") == "true":
                    owner = project.get("owner")
                    repo = project.get("repository")
                    save_path = os.path.expandvars(project.get("save_path"))
                    folder = project.get("folder")
                    files = project.get("files")

                    logging.info(f"即将处理项目: {owner}/{repo}")
                    download_github_file(owner, repo, save_path, folder, files, github_token)
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")
                    logging.info(f"{'-' * 100}")
                else:
                    logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")
                    logging.info(f"{'-' * 100}")
            logging.info("Github 最新文件已下载完成")
            logging.info(f"{'=' * 100}")

    def get_user_input():
        """获取用户输入以选择操作。"""
        nonlocal choice
        choice = input("请输入1、2 或 3 ，当输入其他时，将退出程序：\n")
        timer.cancel()

    input_thread = threading.Thread(target=get_user_input)
    input_thread.start()

    timer.start()

    input_thread.join()

    if choice == '1':
        exec_default_action()

    elif choice == '2':
        print("=" * 100)
        modify_project_status(config, "release")
        logging.info("=" * 100)

    elif choice == '3':
        print("=" * 100)
        modify_project_status(config, "file")
        logging.info("=" * 100)

    else:
        logging.info("=" * 100)
        logging.info("无效的选择，将退出程序")
        logging.info("=" * 100)


if __name__ == "__main__":  # 检查脚本是否直接运行。
    main()  # 执行主函数。
