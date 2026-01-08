from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
import json
import os
import csv
import io
from flask import Response

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-key-please-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///devices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db = SQLAlchemy(app)

# 初始化登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 数据模型 - 修复 UserMixin 继承问题
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    active = db.Column(db.Boolean, default=True)  # 添加 active 字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 添加以下字段用于邀请码系统
    real_name = db.Column(db.String(100))  # 真实姓名
    department = db.Column(db.String(100))  # 部门
    invitation_code_id = db.Column(db.Integer, db.ForeignKey('invitation_code.id'))  # 邀请码ID

    # 关联关系
    invitation_code = db.relationship('InvitationCode', foreign_keys=[invitation_code_id])

    # Flask-Login 需要的属性
    @property
    def is_active(self):
        return self.active
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f'<User {self.username}>'


class InvitationCode(db.Model):
    """邀请码模型"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # 邀请码
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 创建人ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    expires_at = db.Column(db.DateTime)  # 过期时间
    max_uses = db.Column(db.Integer, default=1)  # 最大使用次数
    used_count = db.Column(db.Integer, default=0)  # 已使用次数
    is_active = db.Column(db.Boolean, default=True)  # 是否有效
    notes = db.Column(db.Text)  # 备注

    # 关联关系
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<InvitationCode {self.code}>'

    @property
    def is_expired(self):
        """检查是否过期"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False

    @property
    def can_use(self):
        """检查是否可以使用"""
        return (self.is_active and
                not self.is_expired and
                self.used_count < self.max_uses)

    @property
    def status(self):
        """获取状态文本"""
        if not self.is_active:
            return '已禁用'
        if self.is_expired:
            return '已过期'
        if self.used_count >= self.max_uses:
            return '已用完'
        return '有效'

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    number = db.Column(db.String(100), unique=True, nullable=False)
    model = db.Column(db.String(100))
    info = db.Column(db.Text)
    calibration_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(200))
    manager = db.Column(db.String(100))
    status = db.Column(db.String(20), default='正常')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Device {self.name} - {self.number}>'

class BorrowRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    borrower_name = db.Column(db.String(100), nullable=False)
    borrower_department = db.Column(db.String(100))
    borrower_contact = db.Column(db.String(50))
    borrow_date = db.Column(db.Date, nullable=False)
    expected_return_date = db.Column(db.Date)
    actual_return_date = db.Column(db.Date)
    borrow_purpose = db.Column(db.Text)
    status = db.Column(db.String(20), default='借用中')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    device = db.relationship('Device', backref='borrow_records')
    
    def __repr__(self):
        return f'<BorrowRecord {self.device.name} - {self.borrower_name}>'


@app.route('/devices')
@login_required
def devices():
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    location = request.args.get('location', '')

    query = Device.query

    if search:
        query = query.filter(
            (Device.name.contains(search)) |
            (Device.number.contains(search)) |
            (Device.model.contains(search)) |
            (Device.manager.contains(search))
        )

    if status:
        query = query.filter_by(status=status)

    if location:
        query = query.filter_by(location=location)

    devices_list = query.all()

    # 获取所有唯一的地点用于筛选
    locations = db.session.query(Device.location).distinct().all()
    locations = [loc[0] for loc in locations if loc[0]]

    # 统计信息
    total_devices = Device.query.count()
    available_devices = Device.query.filter_by(status='正常').count()
    borrowed_devices = Device.query.filter_by(status='借用中').count()

    return render_template('devices.html',
                           devices=devices_list,
                           search=search,
                           status=status,
                           location=location,
                           locations=locations,
                           total_devices=total_devices,
                           available_devices=available_devices,
                           borrowed_devices=borrowed_devices)


# ========== 用户注册路由 ==========

@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册（需要邀请码）"""
    # 如果已登录，直接跳转到仪表板
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # 获取表单数据
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        invitation_code = request.form.get('invitation_code', '').strip().upper()  # 邀请码
        real_name = request.form.get('real_name', '')
        department = request.form.get('department', '')

        # 验证输入
        errors = []

        # 检查邀请码
        if not invitation_code:
            errors.append('请输入邀请码')
        else:
            # 验证邀请码
            code_obj = InvitationCode.query.filter_by(code=invitation_code).first()
            if not code_obj:
                errors.append('邀请码无效')
            elif not code_obj.can_use:
                errors.append('邀请码已失效')

        # 检查用户名
        if not username or len(username) < 3:
            errors.append('用户名至少需要3个字符')

        # 检查邮箱格式
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            errors.append('请输入有效的邮箱地址')

        # 检查密码
        if len(password) < 6:
            errors.append('密码至少需要6个字符')
        if password != confirm_password:
            errors.append('两次输入的密码不一致')

        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            errors.append('用户名已存在')

        # 检查邮箱是否已存在
        if User.query.filter_by(email=email).first():
            errors.append('邮箱已被注册')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('register'))

        # 创建新用户
        try:
            new_user = User(
                username=username,
                email=email,
                password=generate_password_hash(password),
                role='user',
                active=True,
                real_name=real_name,
                department=department,
                invitation_code_id=code_obj.id  # 关联邀请码
            )

            # 更新邀请码使用次数
            code_obj.used_count += 1

            db.session.add(new_user)
            db.session.commit()

            # 注册成功后自动登录
            login_user(new_user)
            flash('注册成功！欢迎使用设备管理系统。', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'注册失败：{str(e)}', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')

# 创建数据库表
# 创建数据库表
with app.app_context():
    # 只创建表（如果不存在）
    db.create_all()

    # 检查是否有任何用户存在
    try:
        user_count = User.query.count()

        if user_count == 0:
            # 数据库是空的，创建默认管理员
            admin = User(
                username='admin',
                email='admin@example.com',
                password=generate_password_hash('admin123'),
                role='admin',
                active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ 首次启动：默认管理员账户已创建")
            print("  用户名: admin")
            print("  密码: admin123")
            print("  警告：请立即登录并修改密码！")
        else:
            # 数据库已有用户，不再创建默认管理员
            print(f"✓ 数据库已有 {user_count} 个用户，跳过创建默认管理员")

            # 检查是否有 admin 用户，如果没有，可以创建一个（可选）
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                print("ℹ 提示：系统中没有名为 'admin' 的用户")
    except Exception as e:
        # 如果查询出错，可能是表不存在，但create_all应该已经创建了表
        # 所以这里可能是其他错误
        print(f"⚠ 检查用户时出错: {e}")
        print("ℹ 继续启动应用...")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========== 基本路由 ==========

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            if user.active:  # 检查用户是否激活
                login_user(user, remember=True)
                flash('登录成功！', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('用户账户已被禁用！', 'danger')
        else:
            flash('用户名或密码错误！', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_devices = Device.query.count()
    active_borrows = BorrowRecord.query.filter_by(status='借用中').count()
    available_devices = Device.query.filter_by(status='正常').count()
    
    return render_template('dashboard.html', 
                         total_devices=total_devices,
                         active_borrows=active_borrows,
                         available_devices=available_devices)


@app.route('/device/add', methods=['GET', 'POST'])
@login_required
def add_device():
    if request.method == 'POST':
        try:
            calibration_date = datetime.strptime(
                request.form.get('calibration_date'), 
                '%Y-%m-%d'
            ).date()
        except:
            calibration_date = datetime.now().date()
        
        # 检查设备编号是否已存在
        existing_device = Device.query.filter_by(number=request.form.get('number')).first()
        if existing_device:
            flash('设备编号已存在！', 'danger')
            return redirect(url_for('add_device'))
        
        new_device = Device(
            name=request.form.get('name'),
            number=request.form.get('number'),
            model=request.form.get('model'),
            info=request.form.get('info'),
            calibration_date=calibration_date,
            location=request.form.get('location'),
            manager=request.form.get('manager'),
            status=request.form.get('status', '正常')
        )
        
        db.session.add(new_device)
        db.session.commit()
        
        flash('设备添加成功！', 'success')
        return redirect(url_for('devices'))
    
    return render_template('add_device.html')

@app.route('/device/edit/<int:device_id>', methods=['GET', 'POST'])
@login_required
def edit_device(device_id):
    device = Device.query.get_or_404(device_id)
    
    if request.method == 'POST':
        device.name = request.form.get('name')
        device.number = request.form.get('number')
        device.model = request.form.get('model')
        device.info = request.form.get('info')
        device.calibration_date = datetime.strptime(
            request.form.get('calibration_date'), 
            '%Y-%m-%d'
        ).date()
        device.location = request.form.get('location')
        device.manager = request.form.get('manager')
        device.status = request.form.get('status')
        
        db.session.commit()
        flash('设备信息更新成功！', 'success')
        return redirect(url_for('devices'))
    
    return render_template('edit_device.html', device=device)

@app.route('/device/delete/<int:device_id>', methods=['POST'])
@login_required
def delete_device(device_id):
    if current_user.role != 'admin':
        flash('权限不足！', 'danger')
        return redirect(url_for('devices'))
    
    device = Device.query.get_or_404(device_id)
    device_name = device.name
    
    db.session.delete(device)
    db.session.commit()
    
    flash(f'设备 "{device_name}" 删除成功！', 'success')
    return redirect(url_for('devices'))

# ========== 借用归还路由 ==========

@app.route('/borrow', methods=['GET', 'POST'])
@login_required
def borrow_device():
    if request.method == 'POST':
        device_id = request.form.get('device_id')
        device = Device.query.get_or_404(device_id)
        
        if device.status == '借用中':
            flash('该设备已被借用！', 'danger')
            return redirect(url_for('borrow_device'))
        
        try:
            borrow_date = datetime.strptime(
                request.form.get('borrow_date'), 
                '%Y-%m-%d'
            ).date()
        except:
            borrow_date = datetime.now().date()
        
        borrow_record = BorrowRecord(
            device_id=device_id,
            borrower_name=request.form.get('borrower_name'),
            borrower_department=request.form.get('borrower_department'),
            borrower_contact=request.form.get('borrower_contact'),
            borrow_date=borrow_date,
            borrow_purpose=request.form.get('borrow_purpose'),
            status='借用中'
        )
        
        device.status = '借用中'
        
        db.session.add(borrow_record)
        db.session.commit()
        
        flash('设备借用成功！', 'success')
        return redirect(url_for('borrow_records'))
    
    available_devices = Device.query.filter(Device.status != '借用中').all()
    return render_template('borrow.html', devices=available_devices)

@app.route('/return', methods=['GET', 'POST'])
@login_required
def return_device():
    if request.method == 'POST':
        record_id = request.form.get('record_id')
        borrow_record = BorrowRecord.query.get_or_404(record_id)
        
        borrow_record.actual_return_date = datetime.now().date()
        borrow_record.status = '已归还'
        
        device = borrow_record.device
        device.status = '正常'
        
        db.session.commit()
        flash('设备归还成功！', 'success')
        return redirect(url_for('borrow_records'))
    
    active_records = BorrowRecord.query.filter_by(status='借用中').all()
    return render_template('return.html', records=active_records)

@app.route('/borrow/records')
@login_required
def borrow_records():
    records = BorrowRecord.query.order_by(BorrowRecord.created_at.desc()).all()
    active_records = BorrowRecord.query.filter_by(status='借用中').count()
    returned_records = BorrowRecord.query.filter_by(status='已归还').count()
    
    return render_template('borrow_records.html', 
                         records=records,
                         active_records=active_records,
                         returned_records=returned_records)

# ========== 用户管理路由 ==========

@app.route('/users')
@login_required
def users():
    if current_user.role != 'admin':
        flash('权限不足！', 'danger')
        return redirect(url_for('dashboard'))
    
    users_list = User.query.all()
    return render_template('users.html', users=users_list)

@app.route('/user/add', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': '权限不足'})
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    # 检查用户名是否已存在
    if User.query.filter_by(username=username).first():
        flash('用户名已存在！', 'danger')
        return redirect(url_for('users'))
    
    new_user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role='user',
        active=True
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    flash('用户添加成功！', 'success')
    return redirect(url_for('users'))


# ========== 导出功能路由 ==========

@app.route('/export/devices')
@login_required
def export_devices():
    """导出设备数据为CSV"""
    devices = Device.query.all()

    # 创建CSV内容
    output = io.StringIO()
    writer = csv.writer(output)

    # 写入表头
    writer.writerow(['设备名称', '设备编号', '设备型号', '设备信息', '校准日期',
                     '所在地', '管理人', '状态', '创建时间'])

    # 写入数据
    for device in devices:
        writer.writerow([
            device.name,
            device.number,
            device.model or '',
            device.info or '',
            device.calibration_date.strftime('%Y-%m-%d'),
            device.location or '',
            device.manager or '',
            device.status,
            device.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    output.seek(0)

    # 返回CSV文件
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=devices.csv'}
    )


@app.route('/export/borrow_records')
@login_required
def export_borrow_records():
    """导出借用记录为CSV"""
    records = BorrowRecord.query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    # 写入表头
    writer.writerow(['设备名称', '设备编号', '借用人', '所在部门', '联系方式',
                     '借用日期', '预计归还', '实际归还', '借用用途', '状态'])

    # 写入数据
    for record in records:
        writer.writerow([
            record.device.name,
            record.device.number,
            record.borrower_name,
            record.borrower_department or '',
            record.borrower_contact or '',
            record.borrow_date.strftime('%Y-%m-%d'),
            record.expected_return_date.strftime('%Y-%m-%d') if record.expected_return_date else '',
            record.actual_return_date.strftime('%Y-%m-%d') if record.actual_return_date else '',
            record.borrow_purpose or '',
            record.status
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=borrow_records.csv'}
    )


# ========== 统计API路由 ==========

@app.route('/api/stats')
@login_required
def api_stats():
    """获取系统统计数据"""
    # 设备统计
    total_devices = Device.query.count()
    normal_devices = Device.query.filter_by(status='正常').count()
    borrowed_devices = Device.query.filter_by(status='借用中').count()
    maintenance_devices = Device.query.filter_by(status='维修中').count()

    # 借用统计
    total_borrows = BorrowRecord.query.count()
    active_borrows = BorrowRecord.query.filter_by(status='借用中').count()
    returned_borrows = BorrowRecord.query.filter_by(status='已归还').count()

    # 月度统计
    current_month = datetime.now().month
    current_year = datetime.now().year

    month_borrows = BorrowRecord.query.filter(
        db.extract('year', BorrowRecord.created_at) == current_year,
        db.extract('month', BorrowRecord.created_at) == current_month
    ).count()

    return jsonify({
        'devices': {
            'total': total_devices,
            'normal': normal_devices,
            'borrowed': borrowed_devices,
            'maintenance': maintenance_devices
        },
        'borrows': {
            'total': total_borrows,
            'active': active_borrows,
            'returned': returned_borrows,
            'this_month': month_borrows
        }
    })


# ========== 修改密码和用户名路由 ==========

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """修改当前用户密码"""
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # 验证旧密码
        if not check_password_hash(current_user.password, old_password):
            flash('旧密码错误！', 'danger')
            return redirect(url_for('change_password'))

        # 检查新密码和确认密码是否一致
        if new_password != confirm_password:
            flash('两次输入的新密码不一致！', 'danger')
            return redirect(url_for('change_password'))

        # 检查密码长度
        if len(new_password) < 6:
            flash('新密码至少需要6位！', 'danger')
            return redirect(url_for('change_password'))

        # 更新密码
        current_user.password = generate_password_hash(new_password)
        db.session.commit()

        flash('密码修改成功！请重新登录。', 'success')
        logout_user()
        return redirect(url_for('login'))

    return render_template('change_password.html')


@app.route('/change-username', methods=['GET', 'POST'])
@login_required
def change_username():
    """修改当前用户名"""
    if request.method == 'POST':
        new_username = request.form.get('new_username')

        # 检查新用户名是否已存在
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != current_user.id:
            flash('该用户名已存在！', 'danger')
            return redirect(url_for('change_username'))

        # 检查用户名长度
        if len(new_username) < 3:
            flash('用户名至少需要3位！', 'danger')
            return redirect(url_for('change_username'))

        # 更新用户名
        old_username = current_user.username
        current_user.username = new_username
        db.session.commit()

        flash(f'用户名已从 "{old_username}" 修改为 "{new_username}"！', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_username.html')


# ========== 邀请码管理路由 ==========

@app.route('/admin/invitation-codes')
@login_required
def invitation_codes():
    """邀请码管理页面（仅管理员）"""
    if current_user.role != 'admin':
        flash('权限不足！', 'danger')
        return redirect(url_for('dashboard'))

    # 获取所有邀请码
    codes = InvitationCode.query.order_by(InvitationCode.created_at.desc()).all()

    return render_template('invitation_codes.html', codes=codes)


@app.route('/admin/invitation-code/generate', methods=['POST'])
@login_required
def generate_invitation_code():
    """生成邀请码（仅管理员）"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': '权限不足'})

    try:
        # 获取表单数据
        max_uses = int(request.form.get('max_uses', 1))
        expires_days = int(request.form.get('expires_days', 7))
        notes = request.form.get('notes', '')

        # 生成随机邀请码（8位字母数字）
        import random
        import string

        while True:
            # 生成8位随机码
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # 检查是否已存在
            if not InvitationCode.query.filter_by(code=code).first():
                break

        # 计算过期时间
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

        # 创建邀请码
        invitation = InvitationCode(
            code=code,
            created_by=current_user.id,
            expires_at=expires_at,
            max_uses=max_uses,
            notes=notes,
            is_active=True
        )

        db.session.add(invitation)
        db.session.commit()

        flash(f'邀请码生成成功：{code}', 'success')
        return jsonify({
            'success': True,
            'message': '邀请码生成成功',
            'code': code,
            'expires_at': expires_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'生成失败：{str(e)}'})


@app.route('/admin/invitation-code/toggle/<int:code_id>')
@login_required
def toggle_invitation_code(code_id):
    """启用/禁用邀请码（仅管理员）"""
    if current_user.role != 'admin':
        flash('权限不足！', 'danger')
        return redirect(url_for('invitation_codes'))

    code = InvitationCode.query.get_or_404(code_id)
    code.is_active = not code.is_active

    db.session.commit()

    status = "启用" if code.is_active else "禁用"
    flash(f'邀请码 {code.code} 已{status}', 'success')
    return redirect(url_for('invitation_codes'))


@app.route('/admin/invitation-code/delete/<int:code_id>')
@login_required
def delete_invitation_code(code_id):
    """删除邀请码（仅管理员）"""
    if current_user.role != 'admin':
        flash('权限不足！', 'danger')
        return redirect(url_for('invitation_codes'))

    code = InvitationCode.query.get_or_404(code_id)
    code_value = code.code

    db.session.delete(code)
    db.session.commit()

    flash(f'邀请码 {code_value} 已删除', 'success')
    return redirect(url_for('invitation_codes'))

if __name__ == '__main__':
    print("=" * 50)
    print("设备管理系统启动中...")
    print(f"访问地址: http://127.0.0.1:5000")
    print(f"默认管理员: admin / admin123")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)