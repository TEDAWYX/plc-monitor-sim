"""
数据采集模块

包含采集线程（QThread），负责周期性从 Modbus Client 读取数据，
进行数据校验、加时间戳，并通过 Qt signals 推送到 GUI。
"""
