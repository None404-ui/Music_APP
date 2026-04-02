from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QStackedWidget,
    QWidget,
    QSizePolicy,
    QCheckBox,
)
from PyQt6.QtCore import Qt

from backend.auth import login, register
from backend.remember_login import (
    clear_remembered,
    is_remember_me_enabled,
    load_remembered_credentials,
    save_remembered,
)
from backend.session import UserSession


class AuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("authDialog")
        self.setWindowTitle("CRATES")
        self.setModal(True)
        self.setFixedSize(380, 458)
        self.session: UserSession | None = None

        self._err_login = QLabel("")
        self._err_login.setObjectName("authError")
        self._err_login.setWordWrap(True)

        self._err_reg = QLabel("")
        self._err_reg.setObjectName("authError")
        self._err_reg.setWordWrap(True)

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

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(14)

        title = QLabel("CRATES")
        title.setObjectName("authTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body_layout.addWidget(title)

        self._stack = QStackedWidget()
        self._stack.setObjectName("authStack")

        login_page = self._build_login_page()
        reg_page = self._build_register_page()
        self._stack.addWidget(login_page)
        self._stack.addWidget(reg_page)

        body_layout.addWidget(self._stack, stretch=1)
        chrome_layout.addWidget(body)

        outer.addWidget(chrome)

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("authPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._login_email = QLineEdit()
        self._login_email.setObjectName("authField")
        self._login_email.setPlaceholderText("email")
        lay.addWidget(self._login_email)

        self._login_password = QLineEdit()
        self._login_password.setObjectName("authField")
        self._login_password.setPlaceholderText("пароль")
        self._login_password.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self._login_password)

        self._remember_me = QCheckBox("ЗАПОМНИТЬ МЕНЯ")
        self._remember_me.setObjectName("authRememberCheck")
        self._remember_me.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self._remember_me)

        lay.addWidget(self._err_login)

        btn_in = QPushButton("ВОЙТИ")
        btn_in.setObjectName("authBtnPrimary")
        btn_in.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_in.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_in.clicked.connect(self._on_login)
        lay.addWidget(btn_in)

        btn_reg = QPushButton("СОЗДАТЬ АККАУНТ")
        btn_reg.setObjectName("authBtnSecondary")
        btn_reg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_reg.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reg.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        lay.addWidget(btn_reg)

        lay.addStretch()

        self._apply_saved_login_state()
        return page

    def _build_register_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("authPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._reg_email = QLineEdit()
        self._reg_email.setObjectName("authField")
        self._reg_email.setPlaceholderText("email")
        lay.addWidget(self._reg_email)

        self._reg_password = QLineEdit()
        self._reg_password.setObjectName("authField")
        self._reg_password.setPlaceholderText("пароль")
        self._reg_password.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self._reg_password)

        self._reg_password2 = QLineEdit()
        self._reg_password2.setObjectName("authField")
        self._reg_password2.setPlaceholderText("повторите пароль")
        self._reg_password2.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self._reg_password2)

        lay.addWidget(self._err_reg)

        btn_create = QPushButton("ЗАРЕГИСТРИРОВАТЬСЯ")
        btn_create.setObjectName("authBtnPrimary")
        btn_create.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_create.clicked.connect(self._on_register)
        lay.addWidget(btn_create)

        row = QHBoxLayout()
        back = QPushButton("← Назад к входу")
        back.setObjectName("authBtnLink")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self._back_to_login)
        row.addWidget(back)
        row.addStretch()
        lay.addLayout(row)

        lay.addStretch()
        return page

    def _back_to_login(self):
        self._err_reg.clear()
        self._stack.setCurrentIndex(0)

    def _apply_saved_login_state(self) -> None:
        if is_remember_me_enabled():
            self._remember_me.setChecked(True)
            creds = load_remembered_credentials()
            if creds:
                email, password = creds
                self._login_email.setText(email)
                self._login_password.setText(password)

    def _on_login(self):
        self._err_login.clear()
        email = self._login_email.text()
        password = self._login_password.text()
        s = login(email, password)
        if s is None:
            self._err_login.setText("Неверный email или пароль.")
            return
        if self._remember_me.isChecked():
            save_remembered(email, password)
        else:
            clear_remembered()
        self.session = s
        self.accept()

    def _on_register(self):
        self._err_reg.clear()
        p1 = self._reg_password.text()
        p2 = self._reg_password2.text()
        if p1 != p2:
            self._err_reg.setText("Пароли не совпадают.")
            return
        try:
            self.session = register(self._reg_email.text(), p1)
        except ValueError as e:
            self._err_reg.setText(str(e))
            return
        clear_remembered()
        self._remember_me.setChecked(False)
        self.accept()

    def reject(self):
        self.session = None
        super().reject()
