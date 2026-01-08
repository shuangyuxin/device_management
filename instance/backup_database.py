#!/usr/bin/env python3
"""
数据库备份脚本
可以手动运行或设置为定时任务
"""

import os
import shutil
import datetime
import sys

def backup_database():
    """备份数据库文件"""
    
    # 数据库文件路径
    db_file = 'devices.db'
    
    # 备份目录
    backup_dir = 'backup'
    
    # 如果数据库文件不存在，提示
    if not os.path.exists(db_file):
        print(f"错误：数据库文件 {db_file} 不存在！")
        return False
    
    # 创建备份目录（如果不存在）
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"创建备份目录: {backup_dir}")
    
    # 生成备份文件名（使用当前时间）
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")  # 格式: 20240107_143022
    backup_file = os.path.join(backup_dir, f"devices_backup_{timestamp}.db")
    
    try:
        # 复制数据库文件
        shutil.copy2(db_file, backup_file)
        file_size = os.path.getsize(backup_file) / 1024  # 转换为KB
        
        print("=" * 50)
        print("数据库备份成功！")
        print(f"源文件: {db_file}")
        print(f"备份到: {backup_file}")
        print(f"文件大小: {file_size:.2f} KB")
        print(f"备份时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # 清理旧备份（只保留最近7天的备份）
        cleanup_old_backups(backup_dir, days_to_keep=7)
        
        return True
        
    except Exception as e:
        print(f"备份失败: {e}")
        return False

def cleanup_old_backups(backup_dir, days_to_keep=7):
    """清理超过指定天数的旧备份"""
    
    try:
        now = datetime.datetime.now()
        cutoff_time = now - datetime.timedelta(days=days_to_keep)
        
        deleted_count = 0
        total_saved = 0
        
        # 遍历备份目录中的所有文件
        for filename in os.listdir(backup_dir):
            if filename.startswith("devices_backup_") and filename.endswith(".db"):
                filepath = os.path.join(backup_dir, filename)
                
                # 获取文件修改时间
                file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                
                # 如果文件超过保留天数，删除
                if file_mtime < cutoff_time:
                    file_size = os.path.getsize(filepath) / 1024
                    os.remove(filepath)
                    deleted_count += 1
                    total_saved += file_size
                    print(f"删除旧备份: {filename} ({file_size:.2f} KB)")
        
        if deleted_count > 0:
            print(f"清理完成: 删除了 {deleted_count} 个旧备份，节省 {total_saved:.2f} KB")
            
    except Exception as e:
        print(f"清理旧备份时出错: {e}")

def list_backups():
    """列出所有备份文件"""
    
    backup_dir = 'backup'
    
    if not os.path.exists(backup_dir):
        print("备份目录不存在！")
        return
    
    backups = []
    
    for filename in os.listdir(backup_dir):
        if filename.startswith("devices_backup_") and filename.endswith(".db"):
            filepath = os.path.join(backup_dir, filename)
            file_size = os.path.getsize(filepath) / 1024
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
            
            backups.append({
                'filename': filename,
                'size_kb': file_size,
                'modified': file_mtime,
                'filepath': filepath
            })
    
    if not backups:
        print("没有找到备份文件！")
        return
    
    print("=" * 80)
    print("数据库备份列表")
    print("=" * 80)
    print(f"{'序号':<5} {'备份文件':<30} {'大小(KB)':<10} {'备份时间':<20}")
    print("-" * 80)
    
    backups.sort(key=lambda x: x['modified'], reverse=True)  # 按时间倒序排列
    
    for i, backup in enumerate(backups, 1):
        print(f"{i:<5} {backup['filename']:<30} {backup['size_kb']:<10.2f} {backup['modified'].strftime('%Y-%m-%d %H:%M:%S'):<20}")
    
    print("-" * 80)
    print(f"共 {len(backups)} 个备份文件")
    print("=" * 80)

def restore_backup(backup_number=None, backup_filename=None):
    """恢复数据库备份"""
    
    backup_dir = 'backup'
    
    if not os.path.exists(backup_dir):
        print("备份目录不存在！")
        return False
    
    # 获取备份文件列表
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith("devices_backup_") and filename.endswith(".db"):
            filepath = os.path.join(backup_dir, filename)
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
            
            backups.append({
                'filename': filename,
                'filepath': filepath,
                'modified': file_mtime
            })
    
    if not backups:
        print("没有找到备份文件！")
        return False
    
    backups.sort(key=lambda x: x['modified'], reverse=True)
    
    # 如果没有指定备份文件，显示列表让用户选择
    if backup_filename is None and backup_number is None:
        list_backups()
        try:
            choice = input("\n请输入要恢复的备份序号（或输入 0 取消）: ")
            backup_number = int(choice)
            
            if backup_number == 0:
                print("操作取消。")
                return False
                
            if backup_number < 1 or backup_number > len(backups):
                print("无效的序号！")
                return False
                
            backup_filename = backups[backup_number - 1]['filename']
        except ValueError:
            print("请输入有效的数字！")
            return False
    
    # 如果指定了文件名但没指定完整路径
    elif backup_filename is not None:
        backup_filepath = os.path.join(backup_dir, backup_filename)
        if not os.path.exists(backup_filepath):
            print(f"备份文件 {backup_filename} 不存在！")
            return False
    else:
        # 通过序号查找
        if backup_number < 1 or backup_number > len(backups):
            print("无效的序号！")
            return False
        backup_filename = backups[backup_number - 1]['filename']
        backup_filepath = backups[backup_number - 1]['filepath']
    
    # 备份当前数据库（如果存在）
    current_db = 'devices.db'
    if os.path.exists(current_db):
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_backup = f"devices_temp_backup_{now}.db"
        shutil.copy2(current_db, temp_backup)
        print(f"已备份当前数据库到: {temp_backup}")
    
    try:
        # 恢复备份
        backup_filepath = os.path.join(backup_dir, backup_filename)
        shutil.copy2(backup_filepath, current_db)
        
        print("=" * 50)
        print("数据库恢复成功！")
        print(f"从备份恢复: {backup_filename}")
        print(f"恢复到: {current_db}")
        print(f"恢复时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        print("注意：需要重启应用才能使恢复生效！")
        return True
        
    except Exception as e:
        print(f"恢复失败: {e}")
        return False

def show_help():
    """显示帮助信息"""
    print("=" * 60)
    print("设备管理系统数据库备份工具")
    print("=" * 60)
    print("使用方法:")
    print("  python backup_database.py backup    - 备份当前数据库")
    print("  python backup_database.py list      - 列出所有备份")
    print("  python backup_database.py restore   - 恢复数据库")
    print("  python backup_database.py help      - 显示此帮助")
    print("=" * 60)
    print("示例:")
    print("  python backup_database.py backup")
    print("  python backup_database.py list")
    print("  python backup_database.py restore")
    print("=" * 60)

def main():
    """主函数"""
    
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'backup':
        backup_database()
    elif command == 'list':
        list_backups()
    elif command == 'restore':
        restore_backup()
    elif command == 'help':
        show_help()
    else:
        print(f"未知命令: {command}")
        show_help()

if __name__ == '__main__':
    main()