"""Диалог смены пароля (POST /api/auth/change-password/)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
)

from backend.api_client import CratesApiClient
from backend.remember_login import is_remember_me_enabled, save_remembered
from ui import i18n
from ui.interactive_fx import fade_in_widget


class ChangePasswordDialog(QDialog):
    def __init__(
        self,
        client: CratesApiClient,
        account_email: str,
        parent=None,
    ):
        super().__init__(parent)
        self._client = client
        self._account_email = (account_email or "").strip()
        self.setObjectName("authDialog")
        self.setWindowTitle(i18n.tr("Смена пароля"))
        self.setModal(True)
        self.setFixedSize(380, 420)

        self._err = QLabel("")
        self._err.setObjectName("authError")
        self._err.setWordWrap(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        chrome = QFrame()
        chrome.setObjectName("authChrome")
        chrome_layout = QVBoxLayout(chrome)
        chrome_layout.setContentsMargins(0, 0, 0, 0)
        chrome_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("authHeaderBar")
        chrome_layout.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(24, 20, 24, 20)
        body.setSpacing(12)

        title = QLabel(i18n.tr("Смена пароля"))
        title.setObjectName("authTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(title)

        body.addWidget(self._err)

        self._current = QLineEdit()
        self._current.setObjectName("authField")
        self._current.setPlaceholderText(i18n.tr("Текущий пароль"))
        self._current.setEchoMode(QLineEdit.EchoMode.Password)
        body.addWidget(self._current)

        self._new1 = QLineEdit()
        self._new1.setObjectName("authField")
        self._new1.setPlaceholderText(i18n.tr("Новый пароль"))
        self._new1.setEchoMode(QLineEdit.EchoMode.Password)
        body.addWidget(self._new1)

        self._new2 = QLineEdit()
        self._new2.setObjectName("authField")
        self._new2.setPlaceholderText(i18n.tr("Повторите новый пароль"))
        self._new2.setEchoMode(QLineEdit.EchoMode.Password)
        body.addWidget(self._new2)

        row = QHBoxLayout()
        row.setSpacing(10)
        btn_cancel = QPushButton(i18n.tr("ОТМЕНА"))
        btn_cancel.setObjectName("btnSecondary")
        btn_ok = QPushButton(i18n.tr("СОХРАНИТЬ"))
        btn_ok.setObjectName("btnPrimary")
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self._submit)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        body.addLayout(row)

        chrome_layout.addLayout(body)
        outer.addWidget(chrome)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        fade_in_widget(self)

    def _submit(self) -> None:
        self._err.setText("")
        cur = self._current.text()
        n1 = self._new1.text()
        n2 = self._new2.text()
        if not cur or not n1:
            self._err.setText(i18n.tr("Заполните все поля."))
            return
        if n1 != n2:
            self._err.setText(i18n.tr("Новый пароль и подтверждение не совпадают."))
            return
        if len(n1) < 6:
            self._err.setText(i18n.tr("Пароль не короче 6 символов."))
            return
        st, body = self._client.post_json(
            "/api/auth/change-password/",
            {
                "current_password": cur,
                "new_password": n1,
            },
        )
        if st == 200:
            if is_remember_me_enabled() and self._account_email:
                save_remembered(self._account_email, n1)
            QMessageBox.information(
                self,
                i18n.tr("Смена пароля"),
                i18n.tr("Пароль успешно изменён."),
            )
            self.accept()
            return
        detail = ""
        if isinstance(body, dict):
            detail = str(body.get("detail", body))
        self._err.setText(detail or i18n.tr("Не удалось сменить пароль."))
