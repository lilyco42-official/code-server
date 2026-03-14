from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from models import db
from flask import jsonify, request
from datetime import datetime

login_manager = LoginManager()


def init_login_manager(app):
    login_manager.init_app(app)
    login_manager.login_view = "login"

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "error": "请先登录"}), 401


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
        }


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def register_routes(app):
    @app.route("/api/register", methods=["POST"])
    def register():
        data = request.get_json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        if not username or not email or not password:
            return jsonify({"success": False, "error": "请填写所有字段"})

        if User.query.filter_by(username=username).first():
            return jsonify({"success": False, "error": "用户名已存在"})

        if User.query.filter_by(email=email).first():
            return jsonify({"success": False, "error": "邮箱已被注册"})

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return jsonify({"success": True, "user": user.to_dict()})

    @app.route("/api/login", methods=["POST"])
    def login():
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            return jsonify({"success": False, "error": "用户名或密码错误"})

        login_user(user)
        return jsonify({"success": True, "user": user.to_dict()})

    @app.route("/api/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        return jsonify({"success": True})

    @app.route("/api/current_user")
    def get_current_user():
        if current_user.is_authenticated:
            return jsonify({"success": True, "user": current_user.to_dict()})
        return jsonify({"success": False, "user": None})
