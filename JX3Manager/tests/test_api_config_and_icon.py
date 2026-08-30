import os
import sys
import pytest
from PyQt6.QtWidgets import QApplication, QLineEdit, QMessageBox, QDialog
from PyQt6.QtGui import QIcon

# 确保 offscreen 环境下无图形界面也能测试 Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import JX3Manager
from gui_qt import MainWindow, ConfigDialog, ApiConfigDialog, get_app_icon, APP_ICON_PATH
from readers.baizhan_api import api as bz_api
import config_loader
import gui_qt

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_app_icon_exists_and_valid(qapp):
    """测试应用图标文件存在且能被正确加载为有效 QIcon"""
    assert os.path.exists(APP_ICON_PATH), f"图标文件不存在: {APP_ICON_PATH}"
    icon = get_app_icon()
    assert not icon.isNull(), "QIcon 加载为空"
    sizes = icon.availableSizes()
    assert len(sizes) > 0, "QIcon 没有任何可用尺寸"
    assert sizes[0].width() == 256 and sizes[0].height() == 256

def test_main_window_title_and_api_btn(qapp, monkeypatch):
    """测试主窗口标题含 v1.0，且包含 btn_api_config 按钮"""
    mgr = JX3Manager()
    # 屏蔽 refresh_data 避免在测试时触发真实文件或网络读取
    monkeypatch.setattr(MainWindow, "refresh_data", lambda self: None)
    
    win = MainWindow(mgr)
    assert "v1.0" in win.windowTitle(), f"窗口标题未包含 v1.0: {win.windowTitle()}"
    assert not win.windowIcon().isNull(), "主窗口未设置有效图标"
    
    assert hasattr(win, "btn_api_config"), "MainWindow 缺少 btn_api_config 按钮"
    assert win.btn_api_config.text() == "🔑 API 设置"
    assert "查看或修改 JX3API Token" in win.btn_api_config.toolTip()
    
    win.close()

def test_api_config_dialog_toggle_and_cancel(qapp, monkeypatch):
    """测试 ApiConfigDialog 密码显隐切换与取消"""
    mock_config = {"api_key": "jx3api::test_token_123", "game_path": "C:/dummy"}
    dlg = ApiConfigDialog(mock_config)
    
    assert not dlg.windowIcon().isNull(), "ApiConfigDialog 未设置有效图标"
    assert dlg.token_input.echoMode() == QLineEdit.EchoMode.Password
    assert dlg.btn_toggle_token.text() == "👁 显示"
    
    # 测试显隐切换
    dlg.btn_toggle_token.click()
    assert dlg.token_input.echoMode() == QLineEdit.EchoMode.Normal
    assert dlg.btn_toggle_token.text() == "🙈 隐藏"
    
    dlg.btn_toggle_token.click()
    assert dlg.token_input.echoMode() == QLineEdit.EchoMode.Password
    assert dlg.btn_toggle_token.text() == "👁 显示"
    
    # 测试取消
    dlg.reject()
    assert dlg.result() == QDialog.DialogCode.Rejected
    assert dlg.token_modified is False
    dlg.close()

def test_api_config_dialog_save_unchanged(qapp, monkeypatch):
    """测试 Token 未修改时点击保存直接提示并关闭"""
    mock_config = {"api_key": "jx3api::test_token_123", "game_path": "C:/dummy"}
    dlg = ApiConfigDialog(mock_config)
    
    info_called = []
    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, text: info_called.append((title, text)))
    
    dlg.save()
    assert len(info_called) == 1
    assert "未修改" in info_called[0][1]
    assert dlg.token_modified is False
    dlg.close()

def test_api_config_dialog_save_modified_confirm_yes(qapp, monkeypatch):
    """测试 Token 修改且二次确认选择 Yes 后的保存与运行时同步"""
    mock_config = {"api_key": "jx3api::old_token", "game_path": "C:/dummy"}
    dlg = ApiConfigDialog(mock_config)
    
    dlg.token_input.setText("jx3api::new_token_456")
    
    # 模拟确认对话框点击 Yes
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    
    saved_configs = []
    monkeypatch.setattr(gui_qt, "save_config", lambda cfg: saved_configs.append(cfg.copy()))
    
    dlg.save()
    assert dlg.token_modified is True
    assert mock_config["api_key"] == "jx3api::new_token_456"
    assert bz_api.api_key == "jx3api::new_token_456"
    dlg.close()

def test_api_config_dialog_save_modified_confirm_no(qapp, monkeypatch):
    """测试 Token 修改且二次确认选择 No 时不保存"""
    mock_config = {"api_key": "jx3api::old_token", "game_path": "C:/dummy"}
    dlg = ApiConfigDialog(mock_config)
    
    dlg.token_input.setText("jx3api::new_token_456")
    
    # 模拟确认对话框点击 No
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No)
    
    saved_configs = []
    monkeypatch.setattr(gui_qt, "save_config", lambda cfg: saved_configs.append(cfg.copy()))
    
    dlg.save()
    assert dlg.token_modified is False
    assert mock_config["api_key"] == "jx3api::old_token"
    assert len(saved_configs) == 0
    dlg.close()

def test_config_dialog_features(qapp):
    """测试首启 ConfigDialog 的密码显隐与路径小字提示"""
    mock_config = {"api_key": "test_initial_token", "game_path": ""}
    dlg = ConfigDialog(mock_config)
    
    assert not dlg.windowIcon().isNull(), "ConfigDialog 未设置有效图标"
    assert hasattr(dlg, "btn_toggle_token")
    assert dlg.token_input.echoMode() == QLineEdit.EchoMode.Password
    
    dlg.btn_toggle_token.click()
    assert dlg.token_input.echoMode() == QLineEdit.EchoMode.Normal
    
    from PyQt6.QtWidgets import QLabel
    all_labels = [lbl.text() for lbl in dlg.findChildren(QLabel)]
    found_hint = any("interface" in text and "my#data" in text for text in all_labels)
    assert found_hint, f"ConfigDialog 未包含预期的路径提示小字: {all_labels}"
    dlg.close()
