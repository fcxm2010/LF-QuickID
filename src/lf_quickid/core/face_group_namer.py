from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable

from lf_quickid.core.models import FaceGroup


LogCallback = Callable[[str], None]

_COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟"
    "平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴宋庞熊纪舒屈项祝"
    "董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田"
    "胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石"
    "崔吉龚程嵇邢裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫"
    "乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武"
    "符刘景詹龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池"
    "乔阳胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通"
    "边扈燕冀郏浦尚农温庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾"
    "终暨居衡步都耿满弘匡国文寇广禄阙东欧利师巩聂晁勾敖融冷訾辛阚"
    "那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
)
_COMPOUND_SURNAMES = (
    "欧阳",
    "司马",
    "上官",
    "诸葛",
    "东方",
    "皇甫",
    "尉迟",
    "公羊",
    "澹台",
    "公冶",
    "宗政",
    "濮阳",
    "淳于",
    "单于",
    "太叔",
    "申屠",
    "公孙",
    "仲孙",
    "轩辕",
    "令狐",
    "钟离",
    "宇文",
    "长孙",
    "慕容",
    "鲜于",
    "闾丘",
    "司徒",
    "司空",
    "亓官",
    "司寇",
    "仉督",
    "子车",
    "颛孙",
    "端木",
    "巫马",
    "公西",
    "漆雕",
    "乐正",
    "壤驷",
    "公良",
    "拓跋",
    "夹谷",
    "宰父",
    "谷梁",
    "段干",
    "百里",
    "东郭",
    "南门",
    "呼延",
    "羊舌",
    "微生",
    "梁丘",
    "左丘",
    "东门",
    "西门",
)
_NOISE_WORDS = (
    "微信图片",
    "企业微信",
    "照片",
    "图片",
    "证件照",
    "毕业照",
    "生活照",
    "登记照",
    "电子版",
    "原图",
    "精修",
    "未修",
    "正面",
    "背面",
    "头像",
    "同学",
    "老师",
    "家长",
)
_NOISE_TOKENS = {
    "img",
    "dsc",
    "dscf",
    "mmexport",
    "wx",
    "wechat",
    "image",
    "photo",
    "copy",
    "edited",
    "raw",
    "id",
}
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]+")
_ENGLISH_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:[ _.-]+[A-Z][a-z]+){1,3}\b")


def label_face_groups(groups: list[FaceGroup], log: LogCallback | None = None) -> None:
    for index, group in enumerate(groups, start=1):
        fallback = f"人物 {index}"
        filename_name = best_name_from_paths(_unique_image_paths(group))
        if filename_name:
            group.label = filename_name
            group.label_source = "filename"
            continue

        ocr_name = best_name_from_ocr(group, log)
        if ocr_name:
            group.label = ocr_name
            group.label_source = "ocr"
            continue

        group.label = fallback
        group.label_source = "fallback"


def best_name_from_paths(paths: Iterable[Path]) -> str | None:
    texts = [path.stem for path in paths]
    return best_name_from_texts(texts)


def best_name_from_texts(texts: Iterable[str]) -> str | None:
    ranked: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for order, text in enumerate(texts):
        for candidate in extract_name_candidates(text):
            ranked[candidate] += 1
            first_seen.setdefault(candidate, order)
    if not ranked:
        return None
    return min(ranked, key=lambda item: (-ranked[item], first_seen[item], len(item)))


def extract_name_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    normalized = _normalize_text(text)
    for match in _ENGLISH_NAME_RE.finditer(normalized):
        candidate = " ".join(re.split(r"[ _.-]+", match.group(0).strip()))
        if _is_english_name(candidate):
            candidates.append(candidate)

    for run in _CHINESE_RE.findall(normalized):
        cleaned = _clean_chinese_run(run)
        candidates.extend(_chinese_name_candidates(cleaned))
    return _dedupe(candidates)


def best_name_from_ocr(group: FaceGroup, log: LogCallback | None = None) -> str | None:
    for image_path in _unique_image_paths(group):
        try:
            lines = recognize_text_lines(image_path)
        except TextRecognitionUnavailable as exc:
            if log is not None:
                log(str(exc))
            return None
        except Exception as exc:
            if log is not None:
                log(f"OCR 跳过 {image_path.name}: {exc}")
            continue

        candidate = best_name_from_texts(lines)
        if candidate:
            return candidate
    return None


class TextRecognitionUnavailable(RuntimeError):
    pass


def recognize_text_lines(image_path: Path) -> list[str]:
    try:
        from Foundation import NSURL
        from Quartz import CGImageSourceCreateImageAtIndex, CGImageSourceCreateWithURL
        import Vision
    except Exception as exc:  # pragma: no cover - depends on macOS PyObjC.
        raise TextRecognitionUnavailable("本机 OCR 不可用，已跳过图片文字识别。") from exc

    url = NSURL.fileURLWithPath_(str(image_path))
    source = CGImageSourceCreateWithURL(url, None)
    if source is None:
        raise ValueError("无法读取图片")
    cg_image = CGImageSourceCreateImageAtIndex(source, 0, None)
    if cg_image is None:
        raise ValueError("无法创建 OCR 图片对象")

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    if hasattr(request, "setUsesLanguageCorrection_"):
        request.setUsesLanguageCorrection_(True)
    if hasattr(request, "setRecognitionLanguages_"):
        request.setRecognitionLanguages_(["zh-Hans", "zh-Hant", "en-US"])

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, {})
    result = handler.performRequests_error_([request], None)
    ok = result[0] if isinstance(result, tuple) else result
    if not ok:
        raise ValueError("OCR 识别失败")

    lines: list[str] = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if candidates:
            lines.append(str(candidates[0].string()))
    return lines


def _unique_image_paths(group: FaceGroup) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for face in group.faces:
        if face.image_path in seen:
            continue
        paths.append(face.image_path)
        seen.add(face.image_path)
    return paths


def _normalize_text(text: str) -> str:
    value = text.strip()
    value = re.sub(r"[_\-+.,，。·、()（）\[\]【】{}]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _clean_chinese_run(text: str) -> str:
    cleaned = text
    for word in _NOISE_WORDS:
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(r"\d+", " ", cleaned)
    cleaned = re.sub(r"[一二三四五六七八九十零〇]+班", " ", cleaned)
    return cleaned.replace(" ", "")


def _chinese_name_candidates(text: str) -> list[str]:
    if not text:
        return []
    candidates: list[str] = []
    chunks = [chunk for chunk in re.split(r"\s+", text) if chunk]
    if not chunks:
        chunks = [text]
    for chunk in chunks:
        for start in range(len(chunk)):
            for length in (4, 3, 2):
                value = chunk[start : start + length]
                if len(value) != length:
                    continue
                if _is_chinese_name(value):
                    candidates.append(value)
                    break
    return candidates


def _is_chinese_name(candidate: str) -> bool:
    if not 2 <= len(candidate) <= 4:
        return False
    if not all("\u4e00" <= char <= "\u9fff" for char in candidate):
        return False
    if candidate in _NOISE_WORDS:
        return False
    if any(candidate.endswith(word) for word in ("图片", "照片", "证件", "原图", "正面", "背面")):
        return False
    if any(candidate.startswith(surname) for surname in _COMPOUND_SURNAMES):
        return len(candidate) >= 3
    return candidate[0] in _COMMON_SURNAMES


def _is_english_name(candidate: str) -> bool:
    parts = candidate.split()
    if len(parts) < 2:
        return False
    return not any(part.lower() in _NOISE_TOKENS for part in parts)


def _dedupe(items: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        output.append(item)
        seen.add(item)
    return output
