@echo off
set date=%date:~0,4%%date:~5,2%%date:~8,2%
set time=%time:~0,2%%time:~3,2%%time:~6,2%
copy devices.db backup\devices_%date%_%time%.db
echo 备份完成: devices_%date%_%time%.db