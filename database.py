import sqlite3
import os

# Tạo thư mục 'instance' nếu chưa tồn tại
if not os.path.exists('instance'):
    os.makedirs('instance')

# Kết nối tới database (sẽ tạo file mới nếu chưa có)
conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

# --- XÓA BẢNG CŨ ĐỂ LÀM LẠI TỪ ĐẦU (NẾU CẦN) ---
cursor.execute("DROP TABLE IF EXISTS users")
cursor.execute("DROP TABLE IF EXISTS organizations")
cursor.execute("DROP TABLE IF EXISTS submissions")

# --- TẠO BẢNG TỔ CHỨC ---
cursor.execute('''
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
''')

# --- TẠO BẢNG NGƯỜI DÙNG ---
cursor.execute('''
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    organization_id INTEGER,
    notes TEXT,
    role TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations (id)
)
''')

# --- TẠO BẢNG PHIẾU TRÌNH ---
cursor.execute('''
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations (id),
    FOREIGN KEY (created_by_id) REFERENCES users (id)
)
''')

print("Đã tạo các bảng thành công!")

# --- THÊM DỮ LIỆU MẪU ---

try:
    # Thêm 2 tổ chức mẫu
    cursor.execute("INSERT INTO organizations (name) VALUES (?)", ('Phòng Công nghệ',))
    cursor.execute("INSERT INTO organizations (name) VALUES (?)", ('Phòng Nhân sự',))
    print("Đã thêm các tổ chức mẫu.")

    # Thêm 3 người dùng mặc định
    # admin (không thuộc tổ chức nào)
    cursor.execute(
        "INSERT INTO users (username, password, role, notes) VALUES (?, ?, ?, ?)",
        ('admin', 'admin', 'admin', 'Tài khoản quản trị cao nhất')
    )
    # user1 (người duyệt, thuộc phòng Công nghệ)
    cursor.execute(
        "INSERT INTO users (username, password, organization_id, role, notes) VALUES (?, ?, ?, ?, ?)",
        ('user1', 'user1', 1, 'phe_duyet', 'Người có quyền phê duyệt của Phòng Công nghệ')
    )
    # user2 (người dùng thường, thuộc phòng Nhân sự)
    cursor.execute(
        "INSERT INTO users (username, password, organization_id, role, notes) VALUES (?, ?, ?, ?, ?)",
        ('user2', 'user2', 2, 'binh_thuong', 'Nhân viên phòng Nhân sự')
    )
    print("Đã thêm các người dùng mặc định.")

    # Thêm một phiếu trình mẫu
    cursor.execute(
        "INSERT INTO submissions (organization_id, content, status, created_by_id) VALUES (?, ?, ?, ?)",
        (1, 'Đề xuất mua thêm 02 màn hình Dell UltraSharp cho dự án X.', 'Chờ phê duyệt', 2)
    )
    print("Đã thêm phiếu trình mẫu.")


except sqlite3.IntegrityError as e:
    print(f"Lỗi khi thêm dữ liệu mẫu: {e}. Có thể dữ liệu đã tồn tại.")


# Lưu thay đổi và đóng kết nối
conn.commit()
conn.close()

print("Hoàn tất khởi tạo cơ sở dữ liệu!")