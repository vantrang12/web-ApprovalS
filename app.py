from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_12345'

# Railway sẽ cấp biến môi trường DATABASE_URL (PostgreSQL)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ===================== MODELS =====================
class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    users = db.relationship("User", backref="organization", lazy=True)
    submissions = db.relationship("Submission", backref="organization", lazy=True)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"))
    submissions = db.relationship("Submission", backref="creator", lazy=True)

class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default="Chờ phê duyệt")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

# ===================== DECORATORS =====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "role" not in session or session["role"] != "admin":
            flash("Bạn không có quyền truy cập trang này!", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

# ===================== ROUTES =====================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            session["organization_id"] = user.organization_id
            return redirect(url_for("index"))
        else:
            flash("Tên đăng nhập hoặc mật khẩu không đúng!", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    submissions = (
        db.session.query(Submission)
        .join(Organization, Submission.organization_id == Organization.id)
        .join(User, Submission.created_by_id == User.id)
        .add_columns(
            Submission.id,
            Submission.content,
            Submission.status,
            Organization.name.label("org_name"),
            User.username.label("creator_name"),
        )
        .order_by(Submission.created_at.desc())
        .all()
    )
    return render_template("index.html", submissions=submissions)

@app.route("/tao-phieu-trinh", methods=["GET", "POST"])
@login_required
def tao_phieu_trinh():
    if request.method == "POST":
        content = request.form["content"]
        organization_id = request.form["organization_id"]

        if not content or not organization_id:
            flash("Vui lòng điền đầy đủ thông tin.", "warning")
        else:
            submission = Submission(
                organization_id=organization_id,
                content=content,
                status="Chờ phê duyệt",
                created_by_id=session["user_id"],
            )
            db.session.add(submission)
            db.session.commit()
            flash("Tạo phiếu trình thành công!", "success")
            return redirect(url_for("index"))

    organizations = Organization.query.order_by(Organization.name).all()
    return render_template("tao_phieu_trinh.html", organizations=organizations)

@app.route("/phieu-trinh/<int:id>")
@login_required
def phieu_trinh_chi_tiet(id):
    submission = (
        db.session.query(Submission)
        .join(Organization, Submission.organization_id == Organization.id)
        .join(User, Submission.created_by_id == User.id)
        .filter(Submission.id == id)
        .add_columns(
            Submission.id,
            Submission.content,
            Submission.status,
            Submission.organization_id,
            Organization.name.label("org_name"),
            User.username.label("creator_name"),
        )
        .first()
    )

    can_approve = (
        session["role"] == "phe_duyet"
        and session["organization_id"] == submission.organization_id
        and submission.status == "Chờ phê duyệt"
    )

    return render_template("phieu_trinh_chi_tiet.html", submission=submission, can_approve=can_approve)

@app.route("/phieu-trinh/<int:id>/<action>", methods=["POST"])
@login_required
def action_phieu_trinh(id, action):
    submission = Submission.query.get(id)

    is_approver_for_this = (
        session["role"] == "phe_duyet" and session["organization_id"] == submission.organization_id
    )

    if not is_approver_for_this:
        flash("Bạn không có quyền thực hiện hành động này.", "danger")
        return redirect(url_for("phieu_trinh_chi_tiet", id=id))

    if action == "approve":
        submission.status = "Đã phê duyệt"
        flash("Phiếu trình đã được phê duyệt.", "success")
    elif action == "reject":
        submission.status = "Đã từ chối"
        flash("Phiếu trình đã bị từ chối.", "warning")

    db.session.commit()
    return redirect(url_for("phieu_trinh_chi_tiet", id=id))

@app.route("/admin/users")
@login_required
@admin_required
def quan_ly_nguoi_dung():
    users = (
        db.session.query(User)
        .outerjoin(Organization, User.organization_id == Organization.id)
        .add_columns(User.id, User.username, User.role, Organization.name.label("org_name"))
        .order_by(User.username)
        .all()
    )
    return render_template("quan_ly_nguoi_dung.html", users=users)

@app.route("/admin/user/edit/<int:id>", methods=["GET", "POST"])
@app.route("/admin/user/add", methods=["GET", "POST"], defaults={"id": None})
@login_required
@admin_required
def edit_user(id):
    user = User.query.get(id) if id else None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        organization_id = request.form.get("organization_id") or None
        role = request.form["role"]
        notes = request.form["notes"]

        if id:  # update
            if not password:
                password = user.password
            user.username = username
            user.password = password
            user.organization_id = organization_id
            user.role = role
            user.notes = notes
            flash(f"Cập nhật tài khoản {username} thành công!", "success")
        else:  # create
            if not password:
                flash("Mật khẩu không được để trống khi tạo mới!", "danger")
                return redirect(url_for("edit_user", id=id))
            if User.query.filter_by(username=username).first():
                flash(f"Tên tài khoản {username} đã tồn tại!", "danger")
                return redirect(url_for("edit_user", id=id))
            user = User(username=username, password=password, organization_id=organization_id, role=role, notes=notes)
            db.session.add(user)
            flash(f"Tạo tài khoản {username} thành công!", "success")

        db.session.commit()
        return redirect(url_for("quan_ly_nguoi_dung"))

    organizations = Organization.query.order_by(Organization.name).all()
    return render_template("chi_tiet_nguoi_dung.html", user=user, organizations=organizations)

@app.route("/admin/user/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
def delete_user(id):
    user = User.query.get(id)
    if user.username == "admin":
        flash("Không thể xóa tài khoản admin gốc!", "danger")
        return redirect(url_for("quan_ly_nguoi_dung"))

    db.session.delete(user)
    db.session.commit()
    flash("Đã xóa người dùng thành công.", "success")
    return redirect(url_for("quan_ly_nguoi_dung"))

@app.route("/admin/organizations", methods=["GET", "POST"])
@login_required
@admin_required
def quan_ly_to_chuc():
    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name")
        org_id = request.form.get("id")

        if action == "add":
            if name:
                if Organization.query.filter_by(name=name).first():
                    flash(f"Tổ chức '{name}' đã tồn tại!", "danger")
                else:
                    org = Organization(name=name)
                    db.session.add(org)
                    db.session.commit()
                    flash(f"Đã thêm tổ chức '{name}'.", "success")
        elif action == "edit" and org_id:
            org = Organization.query.get(org_id)
            if org:
                org.name = name
                db.session.commit()
                flash("Đã cập nhật tên tổ chức.", "success")
        elif action == "delete" and org_id:
            org = Organization.query.get(org_id)
            if org and not User.query.filter_by(organization_id=org.id).first():
                db.session.delete(org)
                db.session.commit()
                flash("Đã xóa tổ chức.", "success")
            else:
                flash("Không thể xóa tổ chức vì vẫn còn người dùng thuộc tổ chức này.", "danger")

        return redirect(url_for("quan_ly_to_chuc"))

    organizations = Organization.query.order_by(Organization.name).all()
    return render_template("quan_ly_to_chuc.html", organizations=organizations)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
