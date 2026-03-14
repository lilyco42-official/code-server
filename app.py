import os
import docker
import uuid
import time
import subprocess
from flask import Flask, render_template, request, jsonify
from flask_login import login_required, current_user
from config import Config
from models import db, CodeSnippet
from auth import init_login_manager, register_routes, User

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "dev-secret-key-change-in-production"
db.init_app(app)

init_login_manager(app)
register_routes(app)

try:
    docker_client = docker.from_env()
    DOCKER_AVAILABLE = True
except Exception:
    docker_client = None
    DOCKER_AVAILABLE = False
    print("警告: Docker 不可用，将使用本地执行模式")

LANGUAGE_CONFIG = {
    "python": {"image": "python:3.11-slim", "cmd": ["python3", "-c"]},
    "javascript": {"image": "node:18-slim", "cmd": ["node", "-e"]},
    "java": {"image": "openjdk:17-slim", "cmd": ["java", "Main.java"]},
    "cpp": {"image": "gcc:12-slim", "cmd": ["bash", "-c"]},
    "c": {"image": "gcc:12-slim", "cmd": ["bash", "-c"]},
    "go": {"image": "golang:1.20-slim", "cmd": ["go", "run"]},
    "rust": {"image": "rust:1.70-slim", "cmd": ["bash", "-c"]},
    "ruby": {"image": "ruby:3.2-slim", "cmd": ["ruby", "-e"]},
    "php": {"image": "php:8.2-cli", "cmd": ["php", "-r"]},
    "bash": {"image": "bash:5.2", "cmd": ["bash", "-c"]},
}


def run_code_locally(language, code):
    import tempfile
    import os

    lang_cmds = {
        "python": ["python3", "-c", code],
        "javascript": ["node", "-e", code],
        "bash": ["bash", "-c", code],
        "ruby": ["ruby", "-e", code],
        "php": ["php", "-r", code],
    }

    if language in lang_cmds:
        cmd = lang_cmds[language]
    elif language == "java":
        with tempfile.TemporaryDirectory() as tmpdir:
            java_code = f"public class Main {{ public static void main(String[] args) {{ {code} }} }}"
            with open(os.path.join(tmpdir, "Main.java"), "w") as f:
                f.write(java_code)
            try:
                subprocess.run(
                    ["javac", "Main.java"], cwd=tmpdir, capture_output=True, timeout=30
                )
                result = subprocess.run(
                    ["java", "Main"], cwd=tmpdir, capture_output=True, timeout=30
                )
                return {
                    "success": True,
                    "output": result.stdout.decode(),
                    "exit_code": result.returncode,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
    elif language == "c":
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "main.c"), "w") as f:
                f.write(code)
            try:
                compile_result = subprocess.run(
                    ["gcc", "main.c", "-o", "main"],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=30,
                )
                if compile_result.returncode != 0:
                    return {
                        "success": False,
                        "error": compile_result.stderr.decode() or "编译失败",
                    }
                result = subprocess.run(
                    [os.path.join(tmpdir, "main")],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=30,
                )
                return {
                    "success": True,
                    "output": result.stdout.decode(),
                    "exit_code": result.returncode,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
    elif language == "cpp":
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "main.cpp"), "w") as f:
                f.write(code)
            try:
                compile_result = subprocess.run(
                    ["g++", "main.cpp", "-o", "main"],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=30,
                )
                if compile_result.returncode != 0:
                    return {
                        "success": False,
                        "error": compile_result.stderr.decode() or "编译失败",
                    }
                result = subprocess.run(
                    [os.path.join(tmpdir, "main")],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=30,
                )
                return {
                    "success": True,
                    "output": result.stdout.decode(),
                    "exit_code": result.returncode,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
    elif language == "go":
        with tempfile.TemporaryDirectory() as tmpdir:
            go_code = f"package main\n\nfunc main() {{\n{code}\n}}"
            with open(os.path.join(tmpdir, "main.go"), "w") as f:
                f.write(go_code)
            try:
                result = subprocess.run(
                    ["go", "run", "main.go"],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=30,
                )
                return {
                    "success": True,
                    "output": result.stdout.decode(),
                    "exit_code": result.returncode,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
    elif language == "rust":
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "main.rs"), "w") as f:
                f.write(code)
            try:
                compile_result = subprocess.run(
                    ["rustc", "main.rs", "-o", "main"],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=30,
                )
                if compile_result.returncode != 0:
                    return {"success": False, "error": compile_result.stderr.decode()}
                result = subprocess.run(
                    ["./main"],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=30,
                )
                return {
                    "success": True,
                    "output": result.stdout.decode(),
                    "exit_code": result.returncode,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
    else:
        return {
            "success": False,
            "error": f"本地模式暂不支持 {language}，请使用 Docker 模式",
        }

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
        return {
            "success": True,
            "output": result.stdout or result.stderr,
            "exit_code": result.returncode,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_code_in_docker(language, code):
    if language not in LANGUAGE_CONFIG:
        return {"success": False, "error": f"不支持的语言: {language}"}

    if not DOCKER_AVAILABLE:
        return run_code_locally(language, code)

    config = LANGUAGE_CONFIG[language]
    container_name = f"code-runner-{uuid.uuid4().hex[:8]}"
    cmd = None

    try:
        if language == "python":
            cmd = config["cmd"] + [code]
        elif language == "javascript":
            cmd = config["cmd"] + [code]
        elif language == "java":
            code = f"public class Main {{ public static void main(String[] args) {{ {code} }} }}"
            cmd = [
                "bash",
                "-c",
                f'echo "{code}" > Main.java && javac Main.java && java Main',
            ]
        elif language == "cpp":
            cmd = [
                "bash",
                "-c",
                f'echo "{code}" > main.cpp && g++ main.cpp -o main && ./main',
            ]
        elif language == "c":
            cmd = [
                "bash",
                "-c",
                f'echo "{code}" > main.c && gcc main.c -o main && ./main',
            ]
        elif language == "go":
            cmd = ["go", "run", "main.go"]
            code = f"package main\n\nfunc main() {{\n{code}\n}}"
        elif language == "rust":
            cmd = [
                "bash",
                "-c",
                f'echo "{code}" > main.rs && rustc main.rs -o main && ./main',
            ]
        elif language == "ruby":
            cmd = config["cmd"] + [code]
        elif language == "php":
            cmd = config["cmd"] + [code]
        elif language == "bash":
            cmd = config["cmd"] + [code]

        if cmd is None:
            return {"success": False, "error": "无法构建命令"}

        if not docker_client:
            return {"success": False, "error": "Docker 不可用"}

        if language == "go":
            container = docker_client.containers.run(
                config["image"],
                name=container_name,
                command=cmd,
                detach=True,
                mem_limit="128m",
                cpu_quota=50000,
                network_disabled=True,
                volumes={
                    f"/tmp/code-{container_name}": {"bind": "/code", "mode": "rw"}
                },
            )
            import tarfile
            import io

            tar = io.BytesIO()
            with tarfile.TarFile(fileobj=tar, mode="w") as t:
                t.addfile(tarfile.TarInfo(name="main.go"), io.BytesIO(code.encode()))
            tar.seek(0)
            container.put_archive("/code", tar)
            container.start()
        else:
            container = docker_client.containers.run(
                config["image"],
                name=container_name,
                command=cmd,
                detach=True,
                mem_limit="128m",
                cpu_quota=50000,
                network_disabled=True,
                stderr=True,
                stdout=True,
            )

        result = container.wait(timeout=30)
        logs = container.logs().decode("utf-8")

        container.remove(force=True)

        return {
            "success": True,
            "output": logs,
            "exit_code": result.get("StatusCode", 0),
        }
    except Exception as e:
        try:
            if docker_client:
                container = docker_client.containers.get(container_name)
                container.remove(force=True)
        except:
            pass
        return {"success": False, "error": str(e)}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/run", methods=["POST"])
def run_code():
    import time
    data = request.get_json()
    language = data.get("language", "python")
    code = data.get("code", "")

    if len(code) > app.config["MAX_CODE_LENGTH"]:
        return jsonify(
            {
                "success": False,
                "error": f"代码长度超过限制 ({app.config['MAX_CODE_LENGTH']} 字符)",
            }
        )

    start_time = time.time()
    result = run_code_in_docker(language, code)
    result["duration"] = round((time.time() - start_time) * 1000, 2)
    return jsonify(result)


@app.route("/api/snippets", methods=["GET", "POST"])
@login_required
def handle_snippets():
    if request.method == "POST":
        data = request.get_json()
        snippet = CodeSnippet(
            title=data.get("title", "未命名"),
            language=data.get("language", "python"),
            code=data.get("code", ""),
            user_id=current_user.id,
        )
        db.session.add(snippet)
        db.session.commit()
        return jsonify(snippet.to_dict())
    else:
        snippets = (
            CodeSnippet.query.filter_by(user_id=current_user.id)
            .order_by(CodeSnippet.updated_at.desc())
            .all()
        )
        return jsonify([s.to_dict() for s in snippets])


@app.route("/api/snippets/<int:id>", methods=["GET", "PUT", "DELETE"])
@login_required
def handle_snippet(id):
    snippet = CodeSnippet.query.filter_by(id=id, user_id=current_user.id).first()
    if not snippet:
        return jsonify({"success": False, "error": "代码不存在"}), 404

    if request.method == "PUT":
        data = request.get_json()
        snippet.title = data.get("title", snippet.title)
        snippet.language = data.get("language", snippet.language)
        snippet.code = data.get("code", snippet.code)
        db.session.commit()
        return jsonify(snippet.to_dict())
    elif request.method == "DELETE":
        db.session.delete(snippet)
        db.session.commit()
        return jsonify({"success": True})
    else:
        return jsonify(snippet.to_dict())


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
