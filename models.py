from database import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, user
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    number = db.Column(db.String(100), unique=True, nullable=False)
    model = db.Column(db.String(100))
    info = db.Column(db.Text)
    calibration_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(200))
    manager = db.Column(db.String(100))
    status = db.Column(db.String(20), default='正常')  # 正常, 维修中, 停用
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BorrowRecord(db.Model):
    """设备借用记录"""
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    borrower_name = db.Column(db.String(100), nullable=False)  # 借用人姓名
    borrower_department = db.Column(db.String(100))  # 借用人部门
    borrower_contact = db.Column(db.String(50))  # 联系方式
    borrow_date = db.Column(db.Date, nullable=False)  # 借用日期
    expected_return_date = db.Column(db.Date)  # 预计归还日期
    actual_return_date = db.Column(db.Date)  # 实际归还日期
    borrow_purpose = db.Column(db.Text)  # 借用用途
    borrow_notes = db.Column(db.Text)  # 借用备注
    status = db.Column(db.String(20), default='借用中')  # 借用中、已归还、超期未还
    approver = db.Column(db.String(100))  # 审批人
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # 记录创建人
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

 # 关联关系
    device = db.relationship('Device', backref='borrow_records')
    creator = db.relationship('User')
    
    def __repr__(self):
        return f'<BorrowRecord {self.device.name} - {self.borrower_name}>'
    
    @property
    def is_overdue(self):
        """检查是否超期"""
        if self.status == '借用中' and self.expected_return_date:
            return datetime.now().date() > self.expected_return_date
        return False
    
    @property
    def overdue_days(self):
        """计算超期天数"""
        if self.is_overdue:
            return (datetime.now().date() - self.expected_return_date).days
        return 0