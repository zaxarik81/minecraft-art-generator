from __future__ import annotations

import csv
import gzip
import json
import struct
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageTk


MAP_SIZE = 128
# Sponge Schematic stores Width/Height as signed shorts. The UI therefore
# allows every valid schematic dimension: 1..255 maps per axis (32640 blocks).
MAX_MAPS_PER_SIDE = 255


@dataclass(frozen=True)
class Block:
    name: str
    identifier: str
    group: str
    map_rgb: tuple[int, int, int]


@dataclass(frozen=True)
class MapGroup:
    key: str
    name: str
    rgb: tuple[int, int, int]
    blocks: tuple[tuple[str, str], ...]


# Base map colors for flat Java map art. Blocks are grouped by the color
# Minecraft renders on a map; the UI lets the player choose one material per color.
MAP_GROUPS = [
    MapGroup("snow", "Белый / снег", (255, 255, 255), (("Снежный блок", "minecraft:snow_block"), ("Белый бетон", "minecraft:white_concrete"), ("Белая шерсть", "minecraft:white_wool"), ("Белая терракота", "minecraft:white_terracotta"))),
    MapGroup("quartz", "Кварц", (255, 252, 245), (("Кварцевый блок", "minecraft:quartz_block"), ("Диорит", "minecraft:diorite"), ("Морской фонарь", "minecraft:sea_lantern"))),
    MapGroup("sand", "Песок", (247, 233, 163), (("Песок", "minecraft:sand"), ("Песчаник", "minecraft:sandstone"), ("Берёзовые доски", "minecraft:birch_planks"), ("Светокамень", "minecraft:glowstone"))),
    MapGroup("light_gray", "Светло-серый", (153, 153, 153), (("Светло-серая шерсть", "minecraft:light_gray_wool"), ("Светло-серый бетон", "minecraft:light_gray_concrete"))),
    MapGroup("metal", "Металл", (167, 167, 167), (("Железный блок", "minecraft:iron_block"), ("Наковальня", "minecraft:anvil"))),
    MapGroup("clay", "Глина", (164, 168, 184), (("Глина", "minecraft:clay"), ("Заражённый камень", "minecraft:infested_stone"))),
    MapGroup("stone", "Камень", (112, 112, 112), (("Камень", "minecraft:stone"), ("Андезит", "minecraft:andesite"), ("Булыжник", "minecraft:cobblestone"), ("Гравий", "minecraft:gravel"))),
    MapGroup("gray", "Серый", (76, 76, 76), (("Серая шерсть", "minecraft:gray_wool"), ("Серый бетон", "minecraft:gray_concrete"), ("Мёртвый коралл", "minecraft:dead_brain_coral_block"))),
    MapGroup("black", "Чёрный", (25, 25, 25), (("Чёрная шерсть", "minecraft:black_wool"), ("Чёрный бетон", "minecraft:black_concrete"), ("Обсидиан", "minecraft:obsidian"), ("Угольный блок", "minecraft:coal_block"), ("Базальт", "minecraft:basalt"))),
    MapGroup("dirt", "Земля", (151, 109, 77), (("Земля", "minecraft:dirt"), ("Гранит", "minecraft:granite"), ("Джунглевые доски", "minecraft:jungle_planks"))),
    MapGroup("wood", "Дерево", (143, 119, 72), (("Дубовые доски", "minecraft:oak_planks"), ("Сундук", "minecraft:chest"), ("Верстак", "minecraft:crafting_table"))),
    MapGroup("podzol", "Подзол", (129, 86, 49), (("Еловые доски", "minecraft:spruce_planks"), ("Подзол", "minecraft:podzol"), ("Еловое бревно", "minecraft:spruce_log"))),
    MapGroup("grass", "Трава", (127, 178, 56), (("Блок травы", "minecraft:grass_block"), ("Слизь", "minecraft:slime_block"))),
    MapGroup("plant", "Растения", (0, 124, 0), (("Дубовые листья", "minecraft:oak_leaves"), ("Еловые листья", "minecraft:spruce_leaves"), ("Лианы", "minecraft:vine"))),
    MapGroup("green", "Зелёный", (102, 127, 51), (("Зелёная шерсть", "minecraft:green_wool"), ("Зелёный бетон", "minecraft:green_concrete"), ("Сушёная ламинария", "minecraft:dried_kelp_block"))),
    MapGroup("lime", "Лайм", (127, 204, 25), (("Лаймовая шерсть", "minecraft:lime_wool"), ("Лаймовый бетон", "minecraft:lime_concrete"), ("Арбуз", "minecraft:melon"))),
    MapGroup("yellow", "Жёлтый", (229, 229, 51), (("Жёлтая шерсть", "minecraft:yellow_wool"), ("Жёлтый бетон", "minecraft:yellow_concrete"), ("Сноп сена", "minecraft:hay_block"))),
    MapGroup("gold", "Золото", (250, 238, 77), (("Золотой блок", "minecraft:gold_block"), ("Колокол", "minecraft:bell"))),
    MapGroup("orange", "Оранжевый", (216, 127, 51), (("Оранжевая шерсть", "minecraft:orange_wool"), ("Оранжевый бетон", "minecraft:orange_concrete"), ("Тыква", "minecraft:pumpkin"), ("Красный песок", "minecraft:red_sand"))),
    MapGroup("red", "Красный", (153, 51, 51), (("Красная шерсть", "minecraft:red_wool"), ("Красный бетон", "minecraft:red_concrete"), ("Кирпичи", "minecraft:bricks"), ("Блок красного гриба", "minecraft:red_mushroom_block"))),
    MapGroup("pink", "Розовый", (242, 127, 165), (("Розовая шерсть", "minecraft:pink_wool"), ("Розовый бетон", "minecraft:pink_concrete"), ("Розовый коралл", "minecraft:brain_coral_block"))),
    MapGroup("brown", "Коричневый", (102, 76, 51), (("Коричневая шерсть", "minecraft:brown_wool"), ("Коричневый бетон", "minecraft:brown_concrete"), ("Тёмные дубовые доски", "minecraft:dark_oak_planks"), ("Песок душ", "minecraft:soul_sand"))),
    MapGroup("magenta", "Пурпурный", (178, 76, 216), (("Пурпурная шерсть", "minecraft:magenta_wool"), ("Пурпурный бетон", "minecraft:magenta_concrete"), ("Пурпур", "minecraft:purpur_block"))),
    MapGroup("purple", "Фиолетовый", (127, 63, 178), (("Фиолетовая шерсть", "minecraft:purple_wool"), ("Фиолетовый бетон", "minecraft:purple_concrete"), ("Мицелий", "minecraft:mycelium"))),
    MapGroup("blue", "Синий", (51, 76, 178), (("Синяя шерсть", "minecraft:blue_wool"), ("Синий бетон", "minecraft:blue_concrete"), ("Лазуритовый блок", "minecraft:lapis_block"))),
    MapGroup("light_blue", "Голубой", (102, 153, 216), (("Голубая шерсть", "minecraft:light_blue_wool"), ("Голубой бетон", "minecraft:light_blue_concrete"))),
    MapGroup("cyan", "Бирюзовый", (76, 127, 153), (("Бирюзовая шерсть", "minecraft:cyan_wool"), ("Бирюзовый бетон", "minecraft:cyan_concrete"), ("Призмарин", "minecraft:prismarine"))),
    MapGroup("diamond", "Алмазный", (92, 219, 213), (("Алмазный блок", "minecraft:diamond_block"), ("Маяк", "minecraft:beacon"))),
    MapGroup("lapis", "Лазурит", (74, 128, 255), (("Лазуритовый блок", "minecraft:lapis_block"),)),
    MapGroup("emerald", "Изумрудный", (0, 217, 58), (("Изумрудный блок", "minecraft:emerald_block"),)),
    MapGroup("nether", "Незер", (112, 2, 0), (("Незеррак", "minecraft:netherrack"), ("Незерский кирпич", "minecraft:nether_bricks"), ("Магма", "minecraft:magma_block"))),
    MapGroup("terracotta_black", "Чёрная терракота", (37, 22, 16), (("Чёрная терракота", "minecraft:black_terracotta"),)),
    MapGroup("terracotta_gray", "Серая терракота", (57, 41, 35), (("Серая терракота", "minecraft:gray_terracotta"),)),
    MapGroup("terracotta_red", "Красная терракота", (142, 60, 46), (("Красная терракота", "minecraft:red_terracotta"),)),
    MapGroup("crimson", "Багровый", (189, 48, 49), (("Багровый нилий", "minecraft:crimson_nylium"), ("Багровые доски", "minecraft:crimson_planks"))),
    MapGroup("warped", "Искажённый", (22, 126, 134), (("Искажённый нилий", "minecraft:warped_nylium"), ("Искажённые доски", "minecraft:warped_planks"))),
    MapGroup("deepslate", "Глубинный сланец", (100, 100, 100), (("Глубинный сланец", "minecraft:deepslate"), ("Полированный глубинный сланец", "minecraft:polished_deepslate"))),
]

GROUP_BY_KEY = {group.key: group for group in MAP_GROUPS}
BLOCK_BY_ID = {identifier: Block(name, identifier, group.key, group.rgb) for group in MAP_GROUPS for name, identifier in group.blocks}
DEFAULT_BLOCK_IDS = {identifier for identifier in BLOCK_BY_ID if identifier.endswith("_concrete")}


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _nbt_name(name: str) -> bytes:
    raw = name.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def _nbt_tag(tag_type: int, name: str, payload: bytes) -> bytes:
    return bytes([tag_type]) + _nbt_name(name) + payload


def _nbt_int(name: str, value: int) -> bytes:
    return _nbt_tag(3, name, struct.pack(">i", value))


def _nbt_short(name: str, value: int) -> bytes:
    return _nbt_tag(2, name, struct.pack(">h", value))


def _nbt_string(name: str, value: str) -> bytes:
    raw = value.encode("utf-8")
    return _nbt_tag(8, name, struct.pack(">H", len(raw)) + raw)


def _nbt_byte_array(name: str, data: bytes) -> bytes:
    return _nbt_tag(7, name, struct.pack(">i", len(data)) + data)


def _nbt_compound(name: str, children: bytes) -> bytes:
    return _nbt_tag(10, name, children + b"\x00")


def _write_varint(value: int) -> bytes:
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        result.append(byte | 0x80 if value else byte)
        if not value:
            return bytes(result)


def write_sponge_schematic(path: str, width: int, height: int, length: int, grid: np.ndarray, enabled: list[Block]):
    palette = {"minecraft:air": 0}
    for index, block in enumerate(enabled, start=1):
        palette[block.identifier] = index
    palette_nbt = b"".join(_nbt_int(name, index) for name, index in palette.items())
    # One selected block per map color means the palette fits in a byte. Keep a
    # fallback for future palettes that exceed the one-byte VarInt range.
    values = np.where(grid < 0, 0, grid + 1)
    if len(enabled) < 127:
        block_data = values.astype(np.uint8, copy=False).tobytes(order="C")
    else:
        block_data = b"".join(_write_varint(int(value)) for value in values.ravel(order="C"))
    root = b"".join([
        _nbt_int("Version", 2), _nbt_int("DataVersion", 3465),
        _nbt_short("Width", width), _nbt_short("Height", height), _nbt_short("Length", length),
        _nbt_compound("Palette", palette_nbt), _nbt_byte_array("BlockData", bytes(block_data)),
        _nbt_compound("Metadata", _nbt_string("Name", "MineSchematic")),
    ])
    with gzip.open(path, "wb") as file:
        file.write(bytes([10]) + _nbt_name("Schematic") + root + b"\x00")


class SchematicGenerator(ctk.CTk):
    def __init__(self, pixel_mode: bool = False):
        super().__init__()
        self.pixel_mode = pixel_mode
        self.title("MinePixelArt — генератор пиксель-артов" if pixel_mode else "MineSchematic — генератор 2D-схематик")
        self.geometry("1400x900")
        self.minsize(1120, 720)
        self.configure(fg_color="#10151b")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.source: Image.Image | None = None
        self.grid = np.empty((0, 0), dtype=np.int16)
        self.preview_photo = None
        self.output_width = MAP_SIZE
        self.output_height = MAP_SIZE
        self.group_vars: dict[str, tk.StringVar] = {}
        self.map_x_var = tk.IntVar(value=128 if pixel_mode else 1)
        self.map_z_var = tk.IntVar(value=128 if pixel_mode else 1)
        self.threshold_var = tk.IntVar(value=8)
        self.blur_var = tk.IntVar(value=0)
        self.brightness_var = tk.DoubleVar(value=1.0)
        self.contrast_var = tk.DoubleVar(value=1.0)
        self.saturation_var = tk.DoubleVar(value=1.0)
        self.sharp_var = tk.DoubleVar(value=1.0)
        self.edge_var = tk.StringVar(value="Чёткие края")
        self.background_var = tk.StringVar(value="Прозрачность = воздух")
        self.status_var = tk.StringVar(value="Загрузите изображение, чтобы начать")
        self.info_var = tk.StringVar(value="Нет изображения")
        self.dimension_var = tk.StringVar(value="Размер задаётся в блоках" if pixel_mode else "1 карта = 128 × 128 блоков")
        self.show_map_grid_var = tk.BooleanVar(value=False)
        self.orientation_var = tk.StringVar(value="Вертикальная стена (X × Y)")
        self._render_job = None
        self._build_ui()
        self._make_empty_preview()

    def _build_ui(self):
        header = ctk.CTkFrame(self, height=68, corner_radius=0, fg_color="#151d26")
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="◆  MINE SCHEMATIC", font=ctk.CTkFont(size=24, weight="bold"), text_color="#e9f0f6").pack(side="left", padx=(26, 8))
        ctk.CTkLabel(header, text="генератор 2D-схематик Minecraft", text_color="#81909e", font=ctk.CTkFont(size=14)).pack(side="left")
        ctk.CTkLabel(header, text="Creator: zaxarik81", text_color="#66798a", font=ctk.CTkFont(size=11)).pack(side="left", padx=(16, 0))
        ctk.CTkLabel(header, textvariable=self.status_var, text_color="#70d8a1", font=ctk.CTkFont(size=13)).pack(side="right", padx=26)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=18)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.left = ctk.CTkScrollableFrame(body, width=350, fg_color="#161e27", corner_radius=12)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.preview_panel = ctk.CTkFrame(body, fg_color="#161e27", corner_radius=12)
        self.preview_panel.grid(row=0, column=1, sticky="nsew")
        self.preview_panel.grid_rowconfigure(1, weight=1)
        self.preview_panel.grid_columnconfigure(0, weight=1)
        self._build_controls()
        self._build_preview()

    def _section(self, title: str):
        ctk.CTkLabel(self.left, text=title.upper(), text_color="#7790a3", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=16, pady=(18, 7))

    def _build_controls(self):
        self._section("Изображение")
        ctk.CTkButton(self.left, text="＋  Открыть PNG / JPG / WEBP", height=38, command=self.open_image).pack(fill="x", padx=14)
        ctk.CTkButton(self.left, text="↻  Сбросить изменения", height=30, fg_color="#25313d", hover_color="#314353", command=self.reset_image).pack(fill="x", padx=14, pady=(7, 0))
        ctk.CTkLabel(self.left, textvariable=self.info_var, text_color="#a6b5c2", justify="left", wraplength=305).pack(anchor="w", padx=16, pady=(8, 0))

        self._section("Размер в блоках" if self.pixel_mode else "Размер в картах Minecraft")
        ctk.CTkLabel(self.left, text="Пиксель = один блок" if self.pixel_mode else "Одна карта = 128 × 128 блоков", text_color="#70d8a1").pack(anchor="w", padx=16, pady=(0, 7))
        size_row = ctk.CTkFrame(self.left, fg_color="transparent")
        size_row.pack(fill="x", padx=14)
        ctk.CTkLabel(size_row, text="Ширина в блоках" if self.pixel_mode else "Карт по X").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(size_row, text="Высота в блоках" if self.pixel_mode else "Карт по Z").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ctk.CTkEntry(size_row, textvariable=self.map_x_var, width=105).grid(row=1, column=0, pady=4)
        ctk.CTkEntry(size_row, textvariable=self.map_z_var, width=105).grid(row=1, column=1, padx=(12, 0), pady=4)
        ctk.CTkButton(self.left, text="Применить размер в блоках" if self.pixel_mode else "Применить размер карт", height=30, fg_color="#25313d", hover_color="#314353", command=self.schedule_render).pack(fill="x", padx=14, pady=(2, 0))
        ctk.CTkLabel(self.left, textvariable=self.dimension_var, text_color="#a6b5c2").pack(anchor="w", padx=16, pady=(7, 0))
        ctk.CTkLabel(self.left, text="Ориентация схемы").pack(anchor="w", padx=16, pady=(8, 2))
        ctk.CTkOptionMenu(self.left, values=["Вертикальная стена (X × Y)", "Горизонтальная поверхность (X × Z)"], variable=self.orientation_var, command=lambda _: self.schedule_render()).pack(fill="x", padx=14)
        ctk.CTkCheckBox(self.left, text="Показывать границы карт", variable=self.show_map_grid_var, command=self.draw_preview).pack(anchor="w", padx=14, pady=(7, 0))
        ctk.CTkLabel(self.left, text="Размер ограничен только форматом .schem", text_color="#62798b", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16, pady=(2, 0))

        self._section("Фильтры")
        self._slider("Яркость", self.brightness_var, 0.2, 2.0)
        self._slider("Контраст", self.contrast_var, 0.2, 2.5)
        self._slider("Насыщенность", self.saturation_var, 0.0, 2.5)
        self._slider("Резкость", self.sharp_var, 0.0, 3.0)
        ctk.CTkLabel(self.left, text="Размытие краёв").pack(anchor="w", padx=16, pady=(7, 1))
        ctk.CTkSlider(self.left, from_=0, to=12, number_of_steps=12, variable=self.blur_var, command=lambda _: self.schedule_render()).pack(fill="x", padx=16)
        ctk.CTkOptionMenu(self.left, values=["Чёткие края", "Мягкие края"], variable=self.edge_var, command=lambda _: self.schedule_render()).pack(fill="x", padx=14, pady=(5, 0))

        self._section("Прозрачность")
        ctk.CTkOptionMenu(self.left, values=["Прозрачность = воздух", "Прозрачность = белый блок"], variable=self.background_var, command=lambda _: self.schedule_render()).pack(fill="x", padx=14)
        ctk.CTkSlider(self.left, from_=0, to=255, number_of_steps=255, variable=self.threshold_var, command=lambda _: self.schedule_render()).pack(fill="x", padx=16, pady=(9, 0))
        ctk.CTkLabel(self.left, text="Порог прозрачности", text_color="#8497a8").pack(anchor="w", padx=16)

        self._section("Какие блоки использовать")
        ctk.CTkLabel(self.left, text="Каждая строка — отдельный цвет карты. Выберите конкретный блок для каждого цвета или отключите цвет.", text_color="#a6b5c2", wraplength=305, justify="left").pack(anchor="w", padx=16, pady=(0, 7))
        actions = ctk.CTkFrame(self.left, fg_color="transparent")
        actions.pack(fill="x", padx=14)
        ctk.CTkButton(actions, text="Бетон", width=80, height=28, command=self.select_concrete).pack(side="left")
        ctk.CTkButton(actions, text="Шерсть", width=80, height=28, command=self.select_wool).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Очистить", width=80, height=28, command=self.clear_blocks).pack(side="left")
        for group in MAP_GROUPS:
            row = ctk.CTkFrame(self.left, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(5, 0))
            swatch = "#%02x%02x%02x" % group.rgb
            ctk.CTkLabel(row, text="  ", width=18, fg_color=swatch, corner_radius=3).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(row, text=group.name, width=122, anchor="w", text_color="#d3dde5", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
            var = tk.StringVar(value=self._default_for_group(group))
            self.group_vars[group.key] = var
            values = ["Не использовать"] + [name for name, _ in group.blocks]
            ctk.CTkOptionMenu(row, values=values, variable=var, width=150, command=lambda _: self.schedule_render()).pack(side="left", fill="x", expand=True)

        self._section("Экспорт")
        ctk.CTkButton(self.left, text="▣  Экспорт .schem", height=38, fg_color="#2b9d69", hover_color="#25875b", command=self.export_schem).pack(fill="x", padx=14)
        ctk.CTkButton(self.left, text="▧  Экспорт PNG предпросмотра", height=34, fg_color="#25313d", hover_color="#314353", command=self.export_png).pack(fill="x", padx=14, pady=(7, 0))
        ctk.CTkButton(self.left, text="☷  Экспорт CSV-блоков", height=34, fg_color="#25313d", hover_color="#314353", command=self.export_csv).pack(fill="x", padx=14, pady=(7, 0))

    def _default_for_group(self, group: MapGroup) -> str:
        for name, identifier in group.blocks:
            if identifier in DEFAULT_BLOCK_IDS:
                return name
        return "Не использовать"

    def select_concrete(self):
        for group in MAP_GROUPS:
            self.group_vars[group.key].set(next((name for name, identifier in group.blocks if identifier.endswith("_concrete")), "Не использовать"))
        self.schedule_render()

    def select_wool(self):
        for group in MAP_GROUPS:
            self.group_vars[group.key].set(next((name for name, identifier in group.blocks if identifier.endswith("_wool")), "Не использовать"))
        self.schedule_render()

    def clear_blocks(self):
        for var in self.group_vars.values():
            var.set("Не использовать")
        self.schedule_render()

    def _slider(self, label, variable, low, high):
        ctk.CTkLabel(self.left, text=label).pack(anchor="w", padx=16, pady=(7, 1))
        ctk.CTkSlider(self.left, from_=low, to=high, variable=variable, command=lambda _: self.schedule_render()).pack(fill="x", padx=16)

    def _build_preview(self):
        top = ctk.CTkFrame(self.preview_panel, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(15, 9))
        ctk.CTkLabel(top, text="ПРЕДПРОСМОТР КАРТЫ", font=ctk.CTkFont(size=12, weight="bold"), text_color="#8ea2b4").pack(side="left")
        ctk.CTkLabel(top, text="Цвета показаны как на карте Minecraft", text_color="#66798a", font=ctk.CTkFont(size=11)).pack(side="right")
        self.canvas = tk.Canvas(self.preview_panel, background="#0e1318", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
        self.canvas.bind("<Configure>", lambda _: self.draw_preview())

    def _make_empty_preview(self):
        self.canvas.delete("all")
        w = max(400, self.canvas.winfo_width())
        h = max(300, self.canvas.winfo_height())
        self.canvas.create_text(w // 2, h // 2 - 20, text="Перетащите сюда изображение\nили нажмите «Открыть»", fill="#60798b", font=("Segoe UI", 18), justify="center")
        self.canvas.create_text(w // 2, h // 2 + 45, text="Прозрачность PNG сохраняется как воздух", fill="#435665", font=("Segoe UI", 11))

    def open_image(self):
        path = filedialog.askopenfilename(title="Выберите изображение", filetypes=[("Изображения", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            self.source = Image.open(path).convert("RGBA")
            self.info_var.set(f"{Path(path).name}\n{self.source.width} × {self.source.height} px")
            self.status_var.set("Обработка…")
            self.schedule_render()
        except Exception as exc:
            messagebox.showerror("Не удалось открыть изображение", str(exc))

    def reset_image(self):
        if not self.source:
            return
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.saturation_var.set(1.0)
        self.sharp_var.set(1.0)
        self.blur_var.set(0)
        self.threshold_var.set(8)
        self.edge_var.set("Чёткие края")
        self.schedule_render()

    def schedule_render(self, *_):
        if self._render_job:
            self.after_cancel(self._render_job)
        self._render_job = self.after(120, self.render)

    def _selected_blocks(self) -> list[Block]:
        selected = []
        for group in MAP_GROUPS:
            selected_name = self.group_vars[group.key].get()
            for name, identifier in group.blocks:
                if selected_name == name:
                    selected.append(Block(name, identifier, group.key, group.rgb))
                    break
        return selected or [Block("Белый бетон", "minecraft:white_concrete", "snow", (255, 255, 255))]

    def render(self):
        self._render_job = None
        if not self.source:
            return
        try:
            map_x = clamp(int(self.map_x_var.get()), 1, MAX_MAPS_PER_SIDE * (MAP_SIZE if self.pixel_mode else 1))
            map_z = clamp(int(self.map_z_var.get()), 1, MAX_MAPS_PER_SIDE * (MAP_SIZE if self.pixel_mode else 1))
        except (ValueError, tk.TclError):
            return
        self.map_x_var.set(map_x)
        self.map_z_var.set(map_z)
        width, height = (map_x, map_z) if self.pixel_mode else (map_x * MAP_SIZE, map_z * MAP_SIZE)
        self.output_width, self.output_height = width, height
        plane = "вертикально X×Y" if self.orientation_var.get().startswith("Вертик") else "горизонтально X×Z"
        self.dimension_var.set(f"{width} × {height} блоков · {plane}" if self.pixel_mode else f"{map_x} × {map_z} карт = {width} × {height} блоков · {plane}")
        image = self.source.copy()
        if self.brightness_var.get() != 1: image = ImageEnhance.Brightness(image).enhance(self.brightness_var.get())
        if self.contrast_var.get() != 1: image = ImageEnhance.Contrast(image).enhance(self.contrast_var.get())
        if self.saturation_var.get() != 1: image = ImageEnhance.Color(image).enhance(self.saturation_var.get())
        if self.sharp_var.get() != 1: image = ImageEnhance.Sharpness(image).enhance(self.sharp_var.get())
        if self.blur_var.get() > 0: image = image.filter(ImageFilter.GaussianBlur(radius=self.blur_var.get() / 3))
        image = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.paste(image, ((width - image.width) // 2, (height - image.height) // 2), image)
        if self.edge_var.get() == "Мягкие края":
            canvas.putalpha(canvas.getchannel("A").filter(ImageFilter.GaussianBlur(radius=0.65)))

        enabled = self._selected_blocks()
        pixels = np.asarray(canvas, dtype=np.uint8)
        map_colors = np.asarray([block.map_rgb for block in enabled], dtype=np.int16)
        # Quantize in row chunks. This keeps memory bounded for very large
        # map-art images instead of allocating height*width*palette distances.
        indices = np.empty((height, width), dtype=np.int16)
        chunk_rows = max(1, min(256, 4_000_000 // max(1, width * len(enabled))))
        for start in range(0, height, chunk_rows):
            end = min(height, start + chunk_rows)
            rgb_chunk = pixels[start:end, :, :3].astype(np.int16)
            distances = ((rgb_chunk[:, :, None, :] - map_colors[None, None, :, :]) ** 2).sum(axis=3)
            indices[start:end] = distances.argmin(axis=2)
        transparent = pixels[:, :, 3] < int(self.threshold_var.get())
        if self.background_var.get().startswith("Прозрач"):
            self.grid = np.where(transparent, -1, indices).astype(np.int16, copy=False)
        else:
            self.grid = indices.astype(np.int16, copy=False)
        filled = int(np.count_nonzero(self.grid >= 0))
        self.status_var.set(f"Готово · {map_x}×{map_z} карт · {filled:,} блоков")
        self.draw_preview()

    def draw_preview(self):
        self.canvas.delete("all")
        if self.grid.size == 0:
            self._make_empty_preview()
            return
        cw, ch = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        scale = min((cw - 34) / self.output_width, (ch - 34) / self.output_height)
        x0, y0 = (cw - self.output_width * scale) / 2, (ch - self.output_height * scale) / 2
        enabled = self._selected_blocks()
        palette = np.asarray([block.map_rgb for block in enabled], dtype=np.uint8)
        display_width = max(1, int(self.output_width * scale))
        display_height = max(1, int(self.output_height * scale))
        # For huge projects, sample directly into the visible preview size.
        # The full-resolution grid remains available for schematic export.
        if self.output_width * self.output_height > 4_000_000:
            sample_x = np.linspace(0, self.output_width - 1, display_width, dtype=np.int32)
            sample_y = np.linspace(0, self.output_height - 1, display_height, dtype=np.int32)
            sampled = self.grid[np.ix_(sample_y, sample_x)]
            preview = np.zeros((display_height, display_width, 4), dtype=np.uint8)
            preview[:, :, :3] = palette[np.maximum(sampled, 0)]
            preview[:, :, 3] = 255
            if self.background_var.get().startswith("Прозрач"):
                preview[:, :, 3] = (sampled >= 0).astype(np.uint8) * 255
            rendered = Image.fromarray(preview, "RGBA")
        else:
            indices = np.maximum(self.grid, 0)
            preview = np.zeros((self.output_height, self.output_width, 4), dtype=np.uint8)
            preview[:, :, :3] = palette[indices]
            preview[:, :, 3] = 255
            if self.background_var.get().startswith("Прозрач"):
                preview[:, :, 3] = (self.grid >= 0).astype(np.uint8) * 255
            rendered = Image.fromarray(preview, "RGBA").resize((display_width, display_height), Image.Resampling.NEAREST)
        self.preview_photo = ImageTk.PhotoImage(rendered)
        self.canvas.create_image(x0, y0, image=self.preview_photo, anchor="nw")
        if self.show_map_grid_var.get() and not self.pixel_mode:
            for mx in range(1, int(self.map_x_var.get())):
                self.canvas.create_line(x0 + mx * MAP_SIZE * scale, y0, x0 + mx * MAP_SIZE * scale, y0 + self.output_height * scale, fill="#ffffff", width=1)
            for mz in range(1, int(self.map_z_var.get())):
                self.canvas.create_line(x0, y0 + mz * MAP_SIZE * scale, x0 + self.output_width * scale, y0 + mz * MAP_SIZE * scale, fill="#ffffff", width=1)
            self.canvas.create_rectangle(x0, y0, x0 + self.output_width * scale, y0 + self.output_height * scale, outline="#60798b")

    def _ask_export(self, ext: str, title: str):
        if self.grid.size == 0:
            messagebox.showinfo("Нет схемы", "Сначала откройте изображение и дождитесь обработки.")
            return None
        return filedialog.asksaveasfilename(title=title, defaultextension=ext, filetypes=[(ext.upper(), f"*{ext}")])

    def export_png(self):
        path = self._ask_export(".png", "Экспорт PNG")
        if not path:
            return
        enabled = self._selected_blocks()
        out_array = np.zeros((self.output_height, self.output_width, 4), dtype=np.uint8)
        for index, block in enumerate(enabled):
            mask = self.grid == index
            out_array[mask] = (*block.map_rgb, 255)
        if self.background_var.get().startswith("Прозрач"):
            out_array[self.grid < 0] = (0, 0, 0, 0)
        out = Image.fromarray(out_array, "RGBA")
        out.resize((self.output_width * 4, self.output_height * 4), Image.Resampling.NEAREST).save(path)
        self.status_var.set(f"PNG сохранён: {Path(path).name}")

    def export_csv(self):
        path = self._ask_export(".csv", "Экспорт CSV блоков")
        if not path:
            return
        enabled = self._selected_blocks()
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["z\\x", *range(self.output_width)])
            for y, row in enumerate(self.grid):
                writer.writerow([y, *[enabled[int(value)].identifier if value >= 0 else "minecraft:air" for value in row]])
        self.status_var.set(f"CSV сохранён: {Path(path).name}")

    def export_schem(self):
        path = self._ask_export(".schem", "Экспорт Minecraft Schematic")
        if not path:
            return
        enabled = self._selected_blocks()
        palette = {"minecraft:air": 0, **{block.identifier: index + 1 for index, block in enumerate(enabled)}}
        vertical = self.orientation_var.get().startswith("Вертик")
        schematic_height = self.output_height if vertical else 1
        schematic_length = 1 if vertical else self.output_height
        write_sponge_schematic(path, self.output_width, schematic_height, schematic_length, self.grid, enabled)
        counts = {block.identifier: int(np.count_nonzero(self.grid == index)) for index, block in enumerate(enabled)}
        counts["minecraft:air"] = int(np.count_nonzero(self.grid < 0))
        payload = {"format": "Sponge Schematic v2", "orientation": "vertical_x_y" if vertical else "horizontal_x_z", "width": self.output_width, "height": schematic_height, "length": schematic_length, "image_plane_width": self.output_width, "image_plane_height": self.output_height, "palette": palette, "block_counts": counts}
        if self.pixel_mode:
            payload.update({"size_mode": "blocks", "blocks_x": self.output_width, "blocks_z_or_y": self.output_height})
        else:
            payload.update({"size_mode": "maps", "maps_x": int(self.map_x_var.get()), "maps_z": int(self.map_z_var.get())})
        with open(str(Path(path).with_suffix(".json")), "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        self.status_var.set(f"Схема сохранена: {Path(path).name}")
        orientation_name = "вертикальная стена X×Y" if vertical else "горизонтальная поверхность X×Z"
        size_note = f"Размер: {self.output_width}×{self.output_height} блоков." if self.pixel_mode else "Размер карты: 128×128 блоков."
        messagebox.showinfo("Экспорт завершён", f"Sponge Schematic v2 сохранён.\n\nОриентация: {orientation_name}.\n{size_note}")


if __name__ == "__main__":
    SchematicGenerator(pixel_mode="--pixel" in sys.argv).mainloop()
