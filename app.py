import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_12345'
DATABASE = 'instance/database.db'

# --- KẾT NỐI DATABASE ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Giúp truy cập cột bằng tên
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- DECORATORS (HÀM KIỂM TRA QUYỀN TRUY CẬP) ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Bạn không có quyền truy cập trang này!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- CÁC ROUTE XỬ LÝ CHỨC NĂNG ---

# TRANG ĐĂNG NHẬP / ĐĂNG XUẤT
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?', (username, password)
        ).fetchone()
        
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['organization_id'] = user['organization_id']
            return redirect(url_for('index'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# TRANG CHỦ - DANH SÁCH PHIẾU TRÌNH
@app.route('/')
@login_required
def index():
    db = get_db()
    submissions = db.execute('''
        SELECT s.id, s.content, s.status, o.name as org_name, u.username as creator_name
        FROM submissions s
        JOIN organizations o ON s.organization_id = o.id
        JOIN users u ON s.created_by_id = u.id
        ORDER BY s.created_at DESC
    ''').fetchall()
    return render_template('index.html', submissions=submissions)

# TẠO PHIẾU TRÌNH
@app.route('/tao-phieu-trinh', methods=['GET', 'POST'])
@login_required
def tao_phieu_trinh():
    db = get_db()
    if request.method == 'POST':
        content = request.form['content']
        organization_id = request.form['organization_id']
        
        if not content or not organization_id:
            flash('Vui lòng điền đầy đủ thông tin.', 'warning')
        else:
            db.execute(
                'INSERT INTO submissions (organization_id, content, status, created_by_id) VALUES (?, ?, ?, ?)',
                (organization_id, content, 'Chờ phê duyệt', session['user_id'])
            )
            db.commit()
            flash('Tạo phiếu trình thành công!', 'success')
            return redirect(url_for('index'))

    organizations = db.execute('SELECT * FROM organizations ORDER BY name').fetchall()
    return render_template('tao_phieu_trinh.html', organizations=organizations)

# CHI TIẾT PHIẾU TRÌNH
@app.route('/phieu-trinh/<int:id>')
@login_required
def phieu_trinh_chi_tiet(id):
    db = get_db()
    submission = db.execute('''
        SELECT s.*, o.name as org_name, u.username as creator_name
        FROM submissions s
        JOIN organizations o ON s.organization_id = o.id
        JOIN users u ON s.created_by_id = u.id
        WHERE s.id = ?
    ''', (id,)).fetchone()

    # Kiểm tra xem người dùng có quyền duyệt phiếu này không
    can_approve = (
        session['role'] == 'phe_duyet' and
        session['organization_id'] == submission['organization_id'] and
        submission['status'] == 'Chờ phê duyệt'
    )

    return render_template('phieu_trinh_chi_tiet.html', submission=submission, can_approve=can_approve)

# HÀNH ĐỘNG PHÊ DUYỆT / TỪ CHỐI
@app.route('/phieu-trinh/<int:id>/<action>', methods=['POST'])
@login_required
def action_phieu_trinh(id, action):
    db = get_db()
    submission = db.execute('SELECT * FROM submissions WHERE id = ?', (id,)).fetchone()
    
    # Bảo vệ: Chỉ người có quyền duyệt của đúng tổ chức mới được thực hiện
    is_approver_for_this = (
        session['role'] == 'phe_duyet' and
        session['organization_id'] == submission['organization_id']
    )

    if not is_approver_for_this:
        flash('Bạn không có quyền thực hiện hành động này.', 'danger')
        return redirect(url_for('phieu_trinh_chi_tiet', id=id))

    if action == 'approve':
        new_status = 'Đã phê duyệt'
        flash('Phiếu trình đã được phê duyệt.', 'success')
    elif action == 'reject':
        new_status = 'Đã từ chối'
        flash('Phiếu trình đã bị từ chối.', 'warning')
    else:
        return redirect(url_for('phieu_trinh_chi_tiet', id=id))

    db.execute('UPDATE submissions SET status = ? WHERE id = ?', (new_status, id))
    db.commit()
    return redirect(url_for('phieu_trinh_chi_tiet', id=id))


# --- CÁC CHỨC NĂNG CỦA ADMIN ---

# QUẢN LÝ NGƯỜI DÙNG
@app.route('/admin/users')
@login_required
@admin_required
def quan_ly_nguoi_dung():
    db = get_db()
    users = db.execute('''
        SELECT u.id, u.username, u.role, o.name as org_name
        FROM users u
        LEFT JOIN organizations o ON u.organization_id = o.id
        ORDER BY u.username
    ''').fetchall()
    return render_template('quan_ly_nguoi_dung.html', users=users)

# THÊM / SỬA NGƯỜI DÙNG
@app.route('/admin/user/edit/<int:id>', methods=['GET', 'POST'])
@app.route('/admin/user/add', methods=['GET', 'POST'], defaults={'id': None})
@login_required
@admin_required
def edit_user(id):
    db = get_db()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        organization_id = request.form.get('organization_id')
        role = request.form['role']
        notes = request.form['notes']
        
        # Chuyển '' thành None cho organization_id
        if organization_id == '':
            organization_id = None
        
        if id: # Cập nhật
            user = db.execute('SELECT * FROM users WHERE id = ?', (id,)).fetchone()
            # Nếu không nhập mật khẩu mới thì giữ mật khẩu cũ
            if not password:
                password = user['password']
            db.execute(
                'UPDATE users SET username=?, password=?, organization_id=?, role=?, notes=? WHERE id=?',
                (username, password, organization_id, role, notes, id)
            )
            flash(f'Cập nhật tài khoản {username} thành công!', 'success')
        else: # Thêm mới
            if not password:
                flash('Mật khẩu không được để trống khi tạo mới!', 'danger')
                return redirect(url_for('edit_user', id=id))
            try:
                db.execute(
                    'INSERT INTO users (username, password, organization_id, role, notes) VALUES (?, ?, ?, ?, ?)',
                    (username, password, organization_id, role, notes)
                )
                flash(f'Tạo tài khoản {username} thành công!', 'success')
            except sqlite3.IntegrityError:
                flash(f'Tên tài khoản {username} đã tồn tại!', 'danger')
                return redirect(url_for('edit_user', id=id))

        db.commit()
        return redirect(url_for('quan_ly_nguoi_dung'))

    user = None
    if id:
        user = db.execute('SELECT * FROM users WHERE id = ?', (id,)).fetchone()
    
    organizations = db.execute('SELECT * FROM organizations ORDER BY name').fetchall()
    return render_template('chi_tiet_nguoi_dung.html', user=user, organizations=organizations)

# XÓA NGƯỜI DÙNG
@app.route('/admin/user/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    db = get_db()
    # Không cho xóa tài khoản admin
    user = db.execute('SELECT * FROM users WHERE id = ?', (id,)).fetchone()
    if user['username'] == 'admin':
        flash('Không thể xóa tài khoản admin gốc!', 'danger')
        return redirect(url_for('quan_ly_nguoi_dung'))

    db.execute('DELETE FROM users WHERE id = ?', (id,))
    db.commit()
    flash('Đã xóa người dùng thành công.', 'success')
    return redirect(url_for('quan_ly_nguoi_dung'))

# QUẢN LÝ TỔ CHỨC
@app.route('/admin/organizations', methods=['GET', 'POST'])
@login_required
@admin_required
def quan_ly_to_chuc():
    db = get_db()
    
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('name')
        org_id = request.form.get('id')
        
        if action == 'add':
            if name:
                try:
                    db.execute('INSERT INTO organizations (name) VALUES (?)', (name,))
                    db.commit()
                    flash(f'Đã thêm tổ chức "{name}".', 'success')
                except sqlite3.IntegrityError:
                    flash(f'Tổ chức "{name}" đã tồn tại!', 'danger')
        elif action == 'edit':
            if name and org_id:
                db.execute('UPDATE organizations SET name = ? WHERE id = ?', (name, org_id))
                db.commit()
                flash('Đã cập nhật tên tổ chức.', 'success')
        elif action == 'delete':
            if org_id:
                # Kiểm tra xem có user nào thuộc tổ chức này không
                users_in_org = db.execute('SELECT 1 FROM users WHERE organization_id = ?', (org_id,)).fetchone()
                if users_in_org:
                    flash('Không thể xóa tổ chức vì vẫn còn người dùng thuộc tổ chức này.', 'danger')
                else:
                    db.execute('DELETE FROM organizations WHERE id = ?', (org_id,))
                    db.commit()
                    flash('Đã xóa tổ chức.', 'success')
        
        return redirect(url_for('quan_ly_to_chuc'))

    organizations = db.execute('SELECT * FROM organizations ORDER BY name').fetchall()
    return render_template('quan_ly_to_chuc.html', organizations=organizations)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)