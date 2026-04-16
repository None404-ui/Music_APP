from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.session import UserSession


class UploadMusicDialog(QDialog):
    def __init__(self, session: UserSession, kind: str, parent=None):
        super().__init__(parent)
        self._session = session
        self._kind = kind
        self.created_item: dict | None = None

        self.setObjectName("uploadMusicDialog")
        self.setWindowTitle("Загрузка трека" if kind == "track" else "Загрузка альбома")
        self.resize(520, 320)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        head = QLabel("Загрузить трек" if kind == "track" else "Загрузить альбом")
        head.setObjectName("uploadMusicHead")
        root.addWidget(head)

        hint = QLabel(self._hint_text())
        hint.setObjectName("uploadMusicHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form_wrap = QWidget()
        form = QFormLayout(form_wrap)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        root.addWidget(form_wrap)

        self._title_edit = QLineEdit()
        self._title_edit.setObjectName("authField")
        form.addRow("Название", self._title_edit)

        self._source_edit: QLineEdit | None = None
        if self._kind == "album":
            self._source_edit = QLineEdit()
            self._source_edit.setObjectName("authField")
            self._source_edit.setPlaceholderText(self._source_placeholder())
            source_row = QHBoxLayout()
            source_row.setContentsMargins(0, 0, 0, 0)
            source_row.setSpacing(8)
            source_row.addWidget(self._source_edit, 1)
            self._source_btn = QPushButton("Выбрать")
            self._source_btn.setObjectName("btnSecondary")
            self._source_btn.clicked.connect(self._pick_source)
            source_row.addWidget(self._source_btn)
            form.addRow(self._source_label(), self._wrap(source_row))

        self._audio_edit = QLineEdit()
        self._audio_edit.setObjectName("authField")
        self._audio_edit.setReadOnly(True)
        audio_row = QHBoxLayout()
        audio_row.setContentsMargins(0, 0, 0, 0)
        audio_row.setSpacing(8)
        audio_row.addWidget(self._audio_edit, 1)
        self._audio_btn = QPushButton("Файл")
        self._audio_btn.setObjectName("btnSecondary")
        self._audio_btn.clicked.connect(self._pick_audio_file)
        audio_row.addWidget(self._audio_btn)
        if self._kind == "track":
            form.addRow("Аудиофайл", self._wrap(audio_row))

        self._cover_edit = QLineEdit()
        self._cover_edit.setObjectName("authField")
        self._cover_edit.setReadOnly(True)
        cover_row = QHBoxLayout()
        cover_row.setContentsMargins(0, 0, 0, 0)
        cover_row.setSpacing(8)
        cover_row.addWidget(self._cover_edit, 1)
        self._cover_btn = QPushButton("Обложка")
        self._cover_btn.setObjectName("btnSecondary")
        self._cover_btn.clicked.connect(self._pick_cover_file)
        cover_row.addWidget(self._cover_btn)
        form.addRow("Обложка", self._wrap(cover_row))

        self._error = QLabel("")
        self._error.setObjectName("uploadMusicError")
        self._error.setWordWrap(True)
        self._error.hide()
        root.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("btnSecondary")
        cancel_btn.clicked.connect(self.reject)
        submit_btn = QPushButton("Сохранить")
        submit_btn.setObjectName("btnPrimary")
        submit_btn.clicked.connect(self._submit)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(submit_btn)
        root.addLayout(buttons)

    def _hint_text(self) -> str:
        if self._kind == "track":
            return "Для трека укажите название, выберите аудиофайл и при желании добавьте обложку."
        return (
            "Для альбома укажите ссылку на воспроизведение или выберите папку с треками. "
            "Папка работает, если сервер запущен на этой же машине."
        )

    def _source_label(self) -> str:
        return "Ссылка / папка"

    def _source_placeholder(self) -> str:
        return "https://... или путь к папке"

    @staticmethod
    def _wrap(layout: QHBoxLayout) -> QWidget:
        wrap = QWidget()
        wrap.setLayout(layout)
        return wrap

    def _pick_source(self) -> None:
        if not self._source_edit:
            return
        path = QFileDialog.getExistingDirectory(self, "Папка с треками")
        if path:
            self._source_edit.setText(path)

    def _pick_audio_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Файл трека",
            "",
            "Аудио (*.mp3 *.wav *.flac *.ogg *.m4a *.aac);;Все файлы (*.*)",
        )
        if path:
            self._audio_edit.setText(path)

    def _pick_cover_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Обложка",
            "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)",
        )
        if path:
            self._cover_edit.setText(path)

    def _submit(self) -> None:
        title = self._title_edit.text().strip()
        source = self._source_edit.text().strip() if self._source_edit else ""
        audio = self._audio_edit.text().strip()
        cover = self._cover_edit.text().strip()
        if not title:
            self._show_error("Введите название.")
            return
        if self._kind == "track" and not audio:
            self._show_error("Для трека выберите аудиофайл.")
            return
        if self._kind == "album" and not source:
            self._show_error("Для альбома нужна ссылка или папка с треками.")
            return

        fields = {
            "kind": self._kind,
            "title": title,
        }
        if source:
            fields["playback_ref"] = source
        files: dict[str, str] = {}
        if audio:
            files["audio_file"] = audio
        if cover:
            files["artwork_file"] = cover

        status, body = self._session.client.post_multipart(
            "/api/music-items/",
            fields=fields,
            files=files,
            timeout=120.0,
        )
        if status in (200, 201) and isinstance(body, dict):
            self.created_item = body
            self.accept()
            return

        detail = "Не удалось сохранить запись."
        if isinstance(body, dict):
            detail = str(body.get("detail") or body)
        self._show_error(detail)

    def _show_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.show()
        QMessageBox.warning(self, "Ошибка", text)
