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

# 设置日志文件名称。
log_file = "download_log.txt"

# 如果日志文件不存在，则创建一个新的日志文件。
if not os.path.exists(log_file):
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("")  # 初始化日志文件。

# 控制台输出的格式化器。
console_formatter = logging.Formatter('%(message)s')
# 日志文件输出的格式化器。
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# 文件处理器，用于将日志写入日志文件。
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)  # 设置日志级别为 INFO。
file_handler.setFormatter(file_formatter)  # 为文件日志分配格式化器。

# 控制台处理器，用于输出日志到控制台。
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # 设置日志级别为 INFO。
console_handler.setFormatter(console_formatter)  # 为控制台日志分配格式化器。

# 配置日志设置，包括两个处理器。
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
# 禁用 urllib3 的不安全请求警告。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 定义配置文件名称。
CONFIG_FILE = "config.json"

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

    headers = {}  # 准备请求头。
    if token:  # 如果提供了令牌，则将其添加到请求头中。
        headers['Authorization'] = f'token {token}'

    try:
        def is_file_locked(file_path):
            """检查文件是否被锁定（使用中）。"""
            try:
                with open(file_path, 'a'):  # 尝试以追加模式打开文件。
                    return False  # 如果成功，则文件未被锁定。
            except IOError:
                return True  # 如果发生错误，则文件被锁定。

        if os.path.isfile(file_save_path):  # 如果文件已存在。
            if is_file_locked(file_save_path):  # 检查文件是否被锁定。
                logging.warning(f"{file_name} 已被占用, 尝试重命名为: 【旧版本, 请手动删除】{file_name}")  # 记录警告信息。
                try:
                    os.rename(file_save_path, older_version_file_path)  # 重命名现有文件。
                    logging.info(f"现有文件已重命名为: {older_version_file_path}")  # 记录重命名成功信息。
                except PermissionError:
                    logging.error(f"无法重命名文件: {file_name}, 文件可能正在被占用")  # 记录重命名失败错误。
                    return False  # 退出函数。
                except Exception as e:
                    logging.error(f"重命名文件时发生错误: {e}")  # 记录其他错误。
                    return False  # 退出函数。
            else:
                logging.info(f"{file_name} 已存在, 但未被占用, 将直接下载并覆盖原文件")  # 记录覆盖下载信息。

        response = requests.get(url, headers=headers, stream=True, verify=False)  # 发送 GET 请求下载文件。
        response.raise_for_status()  # 对于错误的响应抛出异常。

        total_size = int(response.headers.get('content-length', 0))  # 获取文件的总大小。
        os.makedirs(save_path, exist_ok=True)  # 如果保存目录不存在，则创建目录。
        with open(file_save_path, 'wb') as f, tqdm(  # 以二进制模式打开文件进行写入。
                desc=file_name,  # 设置进度条描述。
                total=total_size,  # 设置进度条的总大小。
                unit='iB',  # 设置进度条单位。
                unit_scale=True,  # 自动缩放单位。
                unit_divisor=1024,  # 设置单位缩放的除数。
                ncols=100,  # 设置进度条宽度。
                ascii=True) as bar:  # 使用 ASCII 字符表示进度条。
            for chunk in response.iter_content(chunk_size=8192):  # 按块读取响应内容。
                if chunk:
                    f.write(chunk)  # 将块写入文件。
                    bar.update(len(chunk))  # 更新进度条。

        logging.info(f"文件成功下载到: {file_save_path}")  # 记录下载成功信息。

        if file_name.endswith('.zip'):  # 检查文件是否为 zip 格式。
            with zipfile.ZipFile(file_save_path, 'r') as zip_ref:  # 打开 zip 文件。
                zip_ref.extractall(save_path)  # 解压所有内容到保存路径。
            logging.info(f"已成功解压文件: {file_name}")  # 记录解压成功信息。
        elif file_name.endswith('.7z'):  # 检查文件是否为 7z 格式。
            with py7zr.SevenZipFile(file_save_path, mode='r') as archive:  # 打开 7z 文件。
                archive.extractall(path=save_path)  # 解压所有内容到保存路径。
            logging.info(f"已成功解压文件: {file_name}")  # 记录解压成功信息。

    except requests.exceptions.RequestException as e:  # 处理请求相关的错误。
        logging.error(f"下载文件失败: {file_name}. 错误信息: {e}")  # 记录错误信息。
        return False  # 表示失败。
    except Exception as e:  # 处理其他异常。
        logging.error(f"文件下载时发生错误: {e}")  # 记录错误信息。
        return False  # 表示失败。

    finally:  # 清理操作，无论成功或失败都执行。
        if file_name.endswith('.zip') or file_name.endswith('.7z'):  # 检查文件是否为压缩格式。
            if os.path.exists(file_save_path):  # 如果压缩文件存在。
                os.remove(file_save_path)  # 删除压缩文件。
                logging.info(f"已成功删除压缩文件: {file_save_path}")  # 记录删除成功信息。

def download_github_release(owner, repo, version, save_path, files=None, token=None):
    """下载最新的 GitHub Release 文件。"""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"  # 构造获取最新 Release 的 API URL。
    headers = {'Authorization': f'token {token}'} if token else {}  # 如果提供了令牌，则将其添加到请求头。

    try:
        response = requests.get(url, headers=headers)  # 发送 GET 请求获取 Release 信息。
        response.raise_for_status()  # 对于错误的响应抛出异常。

        release = response.json()  # 解析 JSON 响应。
        latest_version = release.get('tag_name', 'unknown')  # 获取最新版本标签。

        if version == "CI":  # 检查版本是否设置为 CI。
            logging.info(f"项目 {owner}/{repo} 版本号为 CI, 将优先下载最新 Release")  # 记录 CI 版本处理信息。
            assets = release.get('assets', [])  # 获取 Release 中的资产列表。
            if assets:  # 如果找到资产。
                for asset in assets:  # 遍历每个资产。
                    file_name = asset['name']  # 获取资产名称。
                    file_url = asset['browser_download_url']  # 获取下载 URL。
                    download_and_unzip(file_url, save_path, file_name, token)  # 下载并解压资产。
            else:
                logging.info(f"项目 {owner}/{repo} 没有可用的 Release, 尝试下载最新的 Artifact")  # 记录没有资产信息。
                download_github_artifact(owner, repo, save_path, token=token)  # 尝试下载 Artifact。
        elif version != latest_version:  # 如果提供的版本不是最新版本。
            assets = release.get('assets', [])  # 获取 Release 中的资产。
            files_to_download = [asset['name'] for asset in assets] if not files else files  # 确定要下载的文件。

            for asset in assets:  # 遍历每个资产。
                file_name = asset['name']  # 获取资产名称。
                if any(fnmatch.fnmatch(file_name, pattern) for pattern in files_to_download):  # 检查是否匹配模式。
                    file_url = asset['browser_download_url']  # 获取下载 URL。
                    download_and_unzip(file_url, save_path, file_name, token)  # 下载并解压资产。

            data = read_or_update_json_file(CONFIG_FILE) or {}  # 读取现有配置或初始化为空。
            for project in data.get("release", []):  # 遍历配置中的 Release 项目。
                if project.get("owner") == owner and project.get("repository") == repo:  # 匹配项目。
                    project["version"] = latest_version  # 更新配置中的版本信息。
            read_or_update_json_file(CONFIG_FILE, data)  # 保存更新的配置。
        else:
            logging.info(f"项目 {owner}/{repo} 本地版本为 {version}, 已是最新, 将跳过下载")  # 记录已是最新版本的信息。
    except (requests.exceptions.RequestException, Exception) as e:  # 处理错误。
        logging.error(f"处理 Release 时发生错误: {e}")  # 记录错误信息。

def download_github_artifact(owner, repo, save_path, token=None):
    """下载 GitHub 的 Artifact 文件。"""
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts"  # 构造获取 Artifact 的 API URL。
    headers = {'Authorization': f'token {token}'} if token else {}  # 如果提供了令牌，则将其添加到请求头。

    try:
        response = requests.get(url, headers=headers)  # 发送 GET 请求获取 Artifact。
        response.raise_for_status()  # 对于错误的响应抛出异常。

        artifacts = response.json().get('artifacts', [])  # 解析 JSON 响应获取 artifacts。
        if artifacts:  # 如果找到 Artifact。
            latest_artifact = artifacts[0]  # 获取最新的 Artifact。
            artifact_url = latest_artifact['archive_download_url']  # 获取下载 URL。
            artifact_name = f"{latest_artifact['name']}.zip"  # 构造 Artifact 文件名。

            download_and_unzip(artifact_url, save_path, artifact_name, token)  # 下载并解压 Artifact。
        else:
            logging.info("未找到 Artifact 文件。")  # 记录没有找到 Artifact 的信息。
    except (requests.exceptions.RequestException, Exception) as e:  # 处理错误。
        logging.error(f"处理 Github Artifact 时, 发生错误: {e}")  # 记录错误信息。

def download_github_file(owner, repo, save_path, folder=None, files=None, token=None):
    """从 GitHub Raw 下载文件，保留文件夹结构，并覆盖已存在的文件。"""
    base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/"  # GitHub 原始文件的基本 URL。

    def download_from_url(file_url, file_path):
        """从 URL 下载单个文件并覆盖已存在的文件。"""
        file_name = os.path.basename(file_path)  # 从路径中获取文件名。
        file_dir = os.path.dirname(file_path)  # 从路径中获取目录。

        if not os.path.exists(file_dir):  # 如果目录不存在。
            os.makedirs(file_dir, exist_ok=True)  # 创建目录。

        download_and_unzip(file_url, file_dir, file_name, token)  # 下载并解压文件。

    def fetch_files_in_folder(folder_url):
        """获取指定文件夹中的所有文件，以便进行通配符匹配。"""
        response = requests.get(folder_url, headers={'Authorization': f'token {token}'} if token else {})  # 发送 GET 请求。
        response.raise_for_status()  # 对于错误的响应抛出异常。
        return response.json()  # 解析并返回 JSON 响应。

    def download_folder_contents(folder_url, folder_path, ignore_folder_structure):
        """递归下载文件夹中的所有文件和子文件夹。"""
        try:
            contents = fetch_files_in_folder(folder_url)  # 获取文件夹内容。

            for item in contents:  # 遍历文件夹中的每个项目。
                item_path = os.path.join(folder_path, item['name'])  # 构造项目的完整路径。
                if item['type'] == 'file':  # 如果项目是文件。
                    file_url = item['download_url']  # 获取下载 URL。
                    if files:  # 如果指定了需要下载的文件。
                        for file_pattern in files:  # 检查模式匹配。
                            if fnmatch.fnmatch(item['name'], file_pattern):  # 匹配文件名。
                                download_from_url(file_url, item_path)  # 下载匹配的文件。
                                break  # 下载后退出循环。
                    else:
                        download_from_url(file_url, item_path)  # 下载未指定文件的文件。
                elif item['type'] == 'dir':  # 如果项目是目录。
                    subfolder_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}"  # 构造子文件夹 URL。
                    new_folder_path = item_path if not ignore_folder_structure else folder_path  # 确定子文件夹的路径。
                    download_folder_contents(subfolder_url, new_folder_path, ignore_folder_structure)  # 递归下载子文件夹内容。
        except requests.exceptions.RequestException as e:  # 处理请求错误。
            logging.error(f"下载 GitHub 文件夹 {folder_path} 时发生错误: {e}")  # 记录错误信息。

    try:
        if files:  # 如果需要下载指定文件。
            if folder:  # 如果指定了特定文件夹。
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents{folder}"  # 构造文件夹 URL。
                folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(os.path.join(save_path, folder))  # 规范化路径。
                os.makedirs(folder_path, exist_ok=True)  # 创建文件夹（如果不存在）。
                download_folder_contents(folder_url, folder_path, folder.startswith('/'))  # 下载文件夹内容。
            else:
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents"  # 根文件夹 URL。
                full_save_path = os.path.normpath(save_path)  # 规范化保存路径。
                os.makedirs(full_save_path, exist_ok=True)  # 创建保存路径文件夹。
                download_folder_contents(folder_url, full_save_path, False)  # 下载根文件夹内容。
        else:  # 如果没有指定文件。
            if folder is None:  # 如果没有指定文件夹。
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents"  # 根文件夹 URL。
                full_save_path = os.path.normpath(save_path)  # 规范化保存路径。
                os.makedirs(full_save_path, exist_ok=True)  # 创建保存路径文件夹。
                download_folder_contents(folder_url, full_save_path, False)  # 下载根文件夹内容。
            else:  # 如果指定了文件夹。
                folder_url = f"https://api.github.com/repos/{owner}/{repo}/contents{folder}"  # 构造文件夹 URL。
                folder_path = os.path.normpath(save_path) if folder.startswith('/') else os.path.normpath(os.path.join(save_path, folder))  # 规范化路径。
                os.makedirs(folder_path, exist_ok=True)  # 创建文件夹（如果不存在）。
                download_folder_contents(folder_url, folder_path, folder.startswith('/'))  # 下载文件夹内容。

    except requests.exceptions.RequestException as e:  # 处理请求错误。
        logging.error(f"下载 GitHub 文件时发生错误: {e}")  # 记录错误信息。

def modify_project_status(config, project_type):
    """显示项目列表，允许用户选择项目并切换其下载功能状态。"""
    projects = config.get(project_type, [])  # 从配置中获取项目列表。

    print(f"项目列表 - {project_type.capitalize()} 项目")  # 打印项目类型标题。
    print("-" * 100)  # 分隔线。
    for i, project in enumerate(projects):  # 遍历项目。
        status_symbol = '√' if project['enabled'] == "true" else '×'  # 确定状态符号。
        print(f"{i + 1}. [{status_symbol}] {'已启用' if project['enabled'] == 'true' else '未启用'}下载功能：{project['owner']}/{project['repository']}（{project.get('description', '')}）")  # 打印项目信息。

    print("-" * 100)  # 分隔线。
    user_input = input("请选择需要启用或禁用下载功能的项目序号（可用空格、英文逗号、中文逗号、分号或斜杠中的任一分隔符分隔多个项目序号）：")  # 获取用户输入。
    print("-" * 100)  # 分隔线。

    selected_indices = [int(i.strip()) - 1 for i in re.split(r'[，,；;/\s]+', user_input) if i.strip().isdigit()]  # 将用户输入解析为有效索引。

    invalid_indices = [i + 1 for i in selected_indices if i < 0 or i >= len(projects)]  # 检查无效索引。
    if invalid_indices:  # 如果存在无效索引。
        print(f"以下序号无效：{', '.join(map(str, invalid_indices))}")  # 打印无效索引。
        return config  # 返回未更改的配置。

    for index in selected_indices:  # 遍历所选索引。
        project = projects[index]  # 获取对应索引的项目。
        new_status = "false" if project["enabled"] == "true" else "true"  # 切换启用状态。
        project["enabled"] = new_status  # 更新项目的启用状态。
        logging.info(f"项目 {project['owner']}/{project['repository']} 的下载已{'启用' if new_status == 'true' else '禁用'}。")  # 记录状态变更。
        logging.info(f"{'-' * 100}")  # 分隔线。

    read_or_update_json_file(CONFIG_FILE, config)  # 保存更新的配置到文件。

def main():
    """主函数，执行下载任务或修改配置。"""
    logging.info(f"{'=' * 100}")  # 记录主函数开始信息。
    config = read_or_update_json_file(CONFIG_FILE)  # 读取配置文件。
    logging.info(f"已读取配置文件: {CONFIG_FILE}")  # 记录读取成功信息。
    logging.info(f"{'=' * 100}")  # 记录分隔线。

    print("请选择操作，3秒内未输入则执行默认操作：")  # 打印操作选项。
    print("-" * 100)  # 分隔线。
    print("1. 更新 Github Release 、下载 Github 文件（默认操作）")  # 选项 1 描述。
    print("2. 修改“是否更新 Github Release”的标识")  # 选项 2 描述。
    print("3. 修改“是否下载 Github 文件”的标识")  # 选项 3 描述。
    print("-" * 100)  # 分隔线。

    choice = None  # 初始化选择变量。
    default_action_executed = False  # 标志，检查默认操作是否已执行。

    timer = threading.Timer(3.0, lambda: (exec_default_action()))  # 定时器，在 3 秒后执行默认操作。

    def exec_default_action():
        """执行默认操作。"""
        print("=" * 100)  # 打印分隔线。
        nonlocal default_action_executed  # 访问外层变量。
        if not default_action_executed:  # 如果默认操作尚未执行。
            default_action_executed = True  # 设置标志为真。
            github_token = config.get("github_token")  # 从配置中获取 GitHub 令牌。

            if github_token:  # 如果令牌可用。
                logging.info("已从 config.json 中加载 GitHub Token")  # 记录令牌加载信息。
                logging.info(f"{'=' * 100}")  # 打印分隔线。
            else:  # 如果没有可用的令牌。
                logging.warning("未在 config.json 中配置 GitHub Token, 下载时将不携带 GitHub Token")  # 记录警告信息。
                logging.info(f"{'=' * 100}")  # 打印分隔线。

            logging.info("即将开始更新 Github 最新 Release")  # 记录开始更新 Release 信息。
            logging.info(f"{'-' * 100}")  # 打印分隔线。
            for project in config.get("release", []):  # 遍历配置中的 Release 项目。
                if project.get("enabled") == "true":  # 如果项目已启用。
                    owner = project.get("owner")  # 获取项目所有者。
                    repo = project.get("repository")  # 获取项目仓库。
                    version = project.get("version")  # 获取项目版本。
                    save_path = os.path.expandvars(project.get("save_path"))  # 扩展保存路径中的环境变量。
                    files = project.get("files")  # 获取要下载的特定文件。
                    logging.info(f"即将处理项目: {owner}/{repo}")  # 记录处理项目信息。
                    download_github_release(owner, repo, version, save_path, files, github_token)  # 下载 Release。
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")  # 记录项目处理完成信息。
                    logging.info(f"{'-' * 100}")  # 打印分隔线。
                else:
                    logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")  # 记录跳过下载的信息。
                    logging.info(f"{'-' * 100}")  # 打印分隔线。
            logging.info("Github 最新 Release 已更新完成")  # 记录更新完成信息。
            logging.info(f"{'=' * 100}")  # 打印分隔线。

            logging.info("即将开始下载 Github 文件")  # 记录开始下载文件的信息。
            logging.info(f"{'-' * 100}")  # 打印分隔线。
            for project in config.get("file", []):  # 遍历配置中的文件项目。
                if project.get("enabled") == "true":  # 如果项目已启用。
                    owner = project.get("owner")  # 获取项目所有者。
                    repo = project.get("repository")  # 获取项目仓库。
                    save_path = os.path.expandvars(project.get("save_path"))  # 扩展保存路径中的环境变量。
                    folder = project.get("folder")  # 获取指定的文件夹路径。
                    files = project.get("files")  # 获取要下载的特定文件。

                    logging.info(f"即将处理项目: {owner}/{repo}")  # 记录处理项目信息。
                    download_github_file(owner, repo, save_path, folder, files, github_token)  # 下载文件。
                    logging.info(f"当前项目已处理完成: {owner}/{repo}")  # 记录项目处理完成信息。
                    logging.info(f"{'-' * 100}")  # 打印分隔线。
                else:
                    logging.info(f"项目 {project.get('owner')}/{project.get('repository')} 未启用下载, 将跳过下载")  # 记录跳过下载的信息。
                    logging.info(f"{'-' * 100}")  # 打印分隔线。
            logging.info("Github 最新文件已下载完成")  # 记录下载完成信息。
            logging.info(f"{'=' * 100}")  # 打印分隔线。

    def get_user_input():
        """获取用户输入以选择操作。"""
        nonlocal choice  # 访问外层变量。
        choice = input("请输入1、2 或 3 ，当输入其他时，将退出程序：\n")  # 提示用户输入。
        timer.cancel()  # 取消定时器。

    input_thread = threading.Thread(target=get_user_input)  # 启动新线程以获取用户输入。
    input_thread.start()  # 启动线程。

    timer.start()  # 启动定时器。

    input_thread.join()  # 等待用户输入线程完成。

    if choice == '1':  # 如果用户选择了选项 1。
        exec_default_action()  # 执行默认操作。

    elif choice == '2':  # 如果用户选择了选项 2。
        print("=" * 100)  # 打印分隔线。
        modify_project_status(config, "release")  # 修改 Release 项目的状态。
        logging.info("=" * 100)  # 打印分隔线。

    elif choice == '3':  # 如果用户选择了选项 3。
        print("=" * 100)  # 打印分隔线。
        modify_project_status(config, "file")  # 修改文件项目的状态。
        logging.info("=" * 100)  # 打印分隔线。

    else:  # 如果用户输入无效。
        logging.info("=" * 100)  # 打印分隔线。
        logging.info("无效的选择，将退出程序")  # 记录无效选择信息。
        logging.info("=" * 100)  # 打印分隔线。

if __name__ == "__main__":  # 检查脚本是否直接运行。
    main()  # 执行主函数。