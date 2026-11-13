"""Tkinter/ttkbootstrap-GUI mit Pad-Raster wie auf dem physischen APC Mini."""
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog

import ttkbootstrap as ttk

from application.command_service import CommandService
from application.led_service import LedService
from domain.exceptions import ApcError, MidiConnectionError
from domain.models import ButtonMapping, DeviceModel, LedColor
from infrastructure.midi_adapter import MidiAdapter
from presentation.i18n import I18nManager

logger = logging.getLogger(__name__)

# Layout-Konstanten gemäß APC Mini Handbuch / deinem Tester
MATRIX_PADS = list(range(64))          # 0..63, 8x8
RIGHT_BUTTONS = list(range(64, 72))    # 64..71, rechte Spalte
BOTTOM_BUTTONS = list(range(82, 90))   # 82..89, untere Reihe

# Farbpalette für den Farbauswahl-Dialog (RGB-Werte, MIDI-konform)
COLOR_PALETTE: dict[str, LedColor] = {
    "Aus":        LedColor(0, 0, 0),
    "Rot":        LedColor(127, 0, 0),
    "Grün":       LedColor(0, 127, 0),
    "Blau":       LedColor(0, 0, 127),
    "Gelb":       LedColor(127, 127, 0),
    "Cyan":       LedColor(0, 127, 127),
    "Magenta":    LedColor(127, 0, 127),
    "Weiß":       LedColor(127, 127, 127),
}


def _rgb_to_hex(color: LedColor) -> str:
    """Wandelt MIDI-RGB (0-127) in einen Hex-String für Tkinter."""
    r = int(color.red / 127 * 255)
    g = int(color.green / 127 * 255)
    b = int(color.blue / 127 * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


def _xy_to_note(x: int, y: int) -> int:
    """Note aus Spalte x (0..7) und Reihe y (0..7, 0=unten) berechnen."""
    return y * 8 + x


class MainWindow(ttk.Window):
    def __init__(self, i18n: I18nManager, midi: MidiAdapter, command_service: CommandService):
        super().__init__(themename="darkly")
        self._i18n = i18n
        self._midi = midi
        self._commands = command_service
        self._led_service: LedService | None = None
        self._poll_job: str | None = None

        # Pad-Widgets und aktueller Zustand (Farbe + Befehl)
        self._pad_buttons: dict[int, ttk.Button] = {}
        self._pad_colors: dict[int, LedColor] = {n: LedColor(0, 0, 0) for n in MATRIX_PADS}
        self._pad_colors.update({n: LedColor(0, 0, 0) for n in RIGHT_BUTTONS})
        self._pad_colors.update({n: LedColor(0, 0, 0) for n in BOTTOM_BUTTONS})

        self.title(self._i18n._("APC Mini Controller"))
        self.geometry("960x720")
        self.minsize(880, 660)
        self._build_ui()
        self._i18n.register_listener(self._retranslate_ui)

    # ---------- UI-Aufbau ----------

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        self._lbl_model = ttk.Label(top, text=self._i18n._("Modell:"))
        self._lbl_model.pack(side="left", padx=(0, 4))

        self._model_var = tk.StringVar(value=DeviceModel.MK1.value)
        self._model_combo = ttk.Combobox(
            top, textvariable=self._model_var,
            values=[m.value for m in DeviceModel], state="readonly", width=18,
        )
        self._model_combo.pack(side="left", padx=(0, 12))

        self._btn_connect = ttk.Button(
            top, text=self._i18n._("Verbinden"),
            command=self._on_connect, bootstyle="success",
        )
        self._btn_connect.pack(side="left", padx=4)

        self._lbl_status = ttk.Label(
            top, text=self._i18n._("Nicht verbunden"), bootstyle="secondary",
        )
        self._lbl_status.pack(side="right")

        # Hauptbereich: links Raster, rechts Befehlstabelle
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Labelframe(main, text=self._i18n._("Befehle"), padding=8)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        self._build_grid(left)
        self._build_command_table(right)

        # Sprachumschalter
        lang_frame = ttk.Frame(self, padding=4)
        lang_frame.pack(fill="x")
        ttk.Button(lang_frame, text="Deutsch",
                   command=lambda: self._i18n.set_language("de"),
                   bootstyle="link").pack(side="left")
        ttk.Button(lang_frame, text="English",
                   command=lambda: self._i18n.set_language("en"),
                   bootstyle="link").pack(side="left")

    def _build_grid(self, parent: ttk.Frame) -> None:
        """Baut das 8x8-Raster + rechte Spalte + untere Reihe."""
        grid_frame = ttk.Labelframe(parent, text=self._i18n._("Pad-Raster"), padding=8)
        grid_frame.pack(fill="both", expand=True)

        # 8x8 Matrix: y=0 (Note 0..7) ganz unten, y=7 (Note 56..63) ganz oben
        for display_row in range(8):
            y = 7 - display_row  # umgekehrt: oben = hohe Noten
            for x in range(8):
                note = _xy_to_note(x, y)
                btn = ttk.Button(
                    grid_frame,
                    text=str(note),
                    width=6,
                    bootstyle="secondary",
                    command=lambda n=note: self._on_pad_left_click(n),
                )
                btn.grid(row=display_row, column=x, padx=2, pady=2, sticky="nsew")
                btn.bind("<Button-3>", lambda e, n=note: self._on_pad_right_click(n, e))
                self._pad_buttons[note] = btn

        # Rechte Spalte: Noten 64..71, oben = 71, unten = 64
        for display_row in range(8):
            note = 71 - display_row
            btn = ttk.Button(
                grid_frame,
                text=str(note),
                width=6,
                bootstyle="secondary",
                command=lambda n=note: self._on_pad_left_click(n),
            )
            btn.grid(row=display_row, column=8, padx=(12, 2), pady=2, sticky="nsew")
            btn.bind("<Button-3>", lambda e, n=note: self._on_pad_right_click(n, e))
            self._pad_buttons[note] = btn

        # Untere Reihe: Noten 82..89
        for x in range(8):
            note = 82 + x
            btn = ttk.Button(
                grid_frame,
                text=str(note),
                width=6,
                bootstyle="secondary",
                command=lambda n=note: self._on_pad_left_click(n),
            )
            btn.grid(row=8, column=x, padx=2, pady=(12, 2), sticky="nsew")
            btn.bind("<Button-3>", lambda e, n=note: self._on_pad_right_click(n, e))
            self._pad_buttons[note] = btn

        # Grid-Gewichte, damit sich das Raster beim Vergrößern ausdehnt
        for c in range(9):
            grid_frame.columnconfigure(c, weight=1)
        for r in range(9):
            grid_frame.rowconfigure(r, weight=1)

        # Legende
        legend = ttk.Frame(grid_frame)
        legend.grid(row=9, column=0, columnspan=9, sticky="w", pady=(8, 0))
        ttk.Label(
            legend,
            text=self._i18n._("Linksklick: Farbe setzen · Rechtsklick: Menü (Farbe/Befehl)"),
            bootstyle="secondary",
        ).pack(side="left")

    def _build_command_table(self, parent: ttk.Labelframe) -> None:
        self._tree = ttk.Treeview(
            parent, columns=("note", "command"), show="headings", height=18,
        )
        self._tree.heading("note", text=self._i18n._("Note"))
        self._tree.heading("command", text=self._i18n._("Befehl"))
        self._tree.column("note", width=60)
        self._tree.column("command", width=240)
        self._tree.pack(fill="both", expand=True)

        btns = ttk.Frame(parent)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text=self._i18n._("Befehl entfernen"),
                   command=self._on_remove_mapping,
                   bootstyle="danger-outline").pack(side="left")

    # ---------- Pad-Interaktion ----------

    def _on_pad_left_click(self, note: int) -> None:
        """Linksklick: setzt die aktuell gewählte Standardfarbe (Rot)."""
        self._apply_color(note, LedColor(127, 0, 0))

    def _on_pad_right_click(self, note: int, event: tk.Event) -> None:
        """Rechtsklick: Kontextmenü mit Farbauswahl, Aus, Befehl zuordnen."""
        menu = tk.Menu(self, tearoff=0)
        color_menu = tk.Menu(menu, tearoff=0)
        for name, color in COLOR_PALETTE.items():
            color_menu.add_command(
                label=self._i18n._(name),
                command=lambda c=color, n=note: self._apply_color(n, c),
            )
        menu.add_cascade(label=self._i18n._("Farbe"), menu=color_menu)
        menu.add_separator()
        menu.add_command(
            label=self._i18n._("Befehl zuordnen…"),
            command=lambda n=note: self._on_assign_command(n),
        )
        if self._commands.get_command(note):
            menu.add_command(
                label=self._i18n._("Befehl entfernen"),
                command=lambda n=note: self._on_remove_mapping_for(n),
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _apply_color(self, note: int, color: LedColor) -> None:
        """Setzt LED am Gerät und aktualisiert die Button-Farbe im UI."""
        if self._led_service is None:
            messagebox.showwarning(
                self._i18n._("Nicht verbunden"),
                self._i18n._("Bitte zuerst verbinden."),
            )
            return
        try:
            self._led_service.set_color(note, color)
            self._update_pad_visual(note, color)
        except (ApcError, ValueError) as exc:
            messagebox.showerror(self._i18n._("Fehler"), str(exc))

    def _update_pad_visual(self, note: int, color: LedColor) -> None:
        """Färbt den Button im Raster passend zur gesetzten LED-Farbe."""
        self._pad_colors[note] = color
        btn = self._pad_buttons.get(note)
        if btn is None:
            return
        hex_color = _rgb_to_hex(color)
        # ttkbootstrap-Buttons unterstützen kein freies bg – wir nutzen ein
        # tk.Button-Fallback? Nein: wir bleiben bei ttk und zeigen die Farbe
        # über den Bootstyle. Einfachster Weg: Text-Hintergrund via style.
        # Da ttk.Button kein direktes bg hat, verwenden wir ein tk.Label-
        # Overlay nicht – stattdessen: wir ändern den Button-Text.
        # Für echte Farbflächen ist ein tk.Button nötig; wir tauschen das
        # Widget aus, um visuelles Feedback zu geben.
        self._replace_with_tk_button(note, hex_color)

    def _replace_with_tk_button(self, note: int, hex_color: str) -> None:
        """Ersetzt den ttk.Button durch ein tk.Button mit echter Hintergrundfarbe.

        ttkbootstrap-Buttons erlauben kein direktes bg – für visuelles Feedback
        ist ein klassischer tk.Button der pragmatischste Weg.
        """
        old = self._pad_buttons.get(note)
        if old is None:
            return
        info = old.grid_info()
        # Bestimme, ob es ein Matrix-Pad, rechter Button oder unterer Button ist
        if note in MATRIX_PADS:
            x = note % 8
            y = note // 8
            display_row = 7 - y
            grid_kw = dict(row=display_row, column=x)
        elif note in RIGHT_BUTTONS:
            display_row = 71 - note
            grid_kw = dict(row=display_row, column=8)
        else:  # BOTTOM_BUTTONS
            x = note - 82
            grid_kw = dict(row=8, column=x)

        new_btn = tk.Button(
            old.master,
            text=str(note),
            bg=hex_color,
            fg="white" if self._is_dark(hex_color) else "black",
            activebackground=hex_color,
            relief="raised",
            bd=2,
            command=lambda n=note: self._on_pad_left_click(n),
        )
        padx = info.get("padx", 2)
        pady = info.get("pady", 2)
        sticky = info.get("sticky", "nsew")
        new_btn.grid(row=grid_kw["row"], column=grid_kw["column"],
                     padx=padx, pady=pady, sticky=sticky)
        new_btn.bind("<Button-3>", lambda e, n=note: self._on_pad_right_click(n, e))
        old.destroy()
        self._pad_buttons[note] = new_btn  # type: ignore[assignment]

    @staticmethod
    def _is_dark(hex_color: str) -> bool:
        """Grobe Helligkeitsprüfung für Textfarbe auf dem Button."""
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
        except (ValueError, IndexError):
            return True
        return (r * 299 + g * 587 + b * 114) / 1000 < 128

    # ---------- Befehlszuordnung ----------

    def _on_assign_command(self, note: int) -> None:
        cmd = simpledialog.askstring(
            self._i18n._("Befehl zuordnen"),
            self._i18n._("Windows-Befehl für Note {note}:").format(note=note),
            parent=self,
        )
        if not cmd:
            return
        self._commands.register(ButtonMapping(note=note, command=cmd))
        self._refresh_command_table()

    def _on_remove_mapping(self) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        note_str = self._tree.item(sel[0], "values")[0]
        try:
            note = int(note_str)
        except ValueError:
            return
        self._commands.unregister(note)
        self._refresh_command_table()

    def _on_remove_mapping_for(self, note: int) -> None:
        self._commands.unregister(note)
        self._refresh_command_table()

    def _refresh_command_table(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for note in sorted(self._commands._mappings.keys()):
            m = self._commands._mappings[note]
            self._tree.insert("", "end", values=(m.note, m.command))

    # ---------- Sprache ----------

    def _retranslate_ui(self) -> None:
        self.title(self._i18n._("APC Mini Controller"))
        self._lbl_model.configure(text=self._i18n._("Modell:"))
        self._btn_connect.configure(text=self._i18n._("Verbinden"))
        self._tree.heading("note", text=self._i18n._("Note"))
        self._tree.heading("command", text=self._i18n._("Befehl"))

    # ---------- Verbindung & Polling ----------

    def _on_connect(self) -> None:
        model_str = self._model_var.get()
        model = next(m for m in DeviceModel if m.value == model_str)
        try:
            self._midi.connect()
            self._led_service = LedService(self._midi, model)
            self._lbl_status.configure(
                text=self._i18n._("Verbunden"), bootstyle="success",
            )
            self._btn_connect.configure(state="disabled")
            self._start_polling()
            # Visuelles Feedback: Pad 0 rot
            self._apply_color(0, LedColor(127, 0, 0))
        except MidiConnectionError as exc:
            messagebox.showerror(self._i18n._("MIDI-Fehler"), str(exc))

    def _start_polling(self) -> None:
        if self._midi is None:
            return
        try:
            note = self._midi.poll_input()
            if note is not None:
                self._commands.execute(note)
                # Visuelles Feedback: kurz aufblinken im UI
                self._flash_pad(note)
        except ApcError as exc:
            logger.error("Befehlsfehler: %s", exc)
        except Exception as exc:
            logger.error("Polling-Fehler: %s", exc)
        finally:
            self._poll_job = self.after(50, self._start_polling)

    def _flash_pad(self, note: int) -> None:
        """Lässt das Pad im UI kurz hell aufleuchten, wenn es gedrückt wird."""
        btn = self._pad_buttons.get(note)
        if btn is None or not isinstance(btn, tk.Button):
            return
        original = btn.cget("bg")
        btn.configure(bg="#ffffff")
        self.after(120, lambda: btn.configure(bg=original))

    def destroy(self) -> None:
        if self._poll_job:
            self.after_cancel(self._poll_job)
        self._midi.close()
        super().destroy()