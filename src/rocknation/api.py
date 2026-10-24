"""Client for the MP3 section of https://rocknation.su/ (HTML scraping)."""

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote, unquote, urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://rocknation.su"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
)

_BAND_RE = re.compile(r"/mp3/band-(\d+)")
_ALBUM_RE = re.compile(r"/mp3/album-(\d+)")
_GENRE_RE = re.compile(r"/mp3/genre-(\d+)")
_PAGE_RE = re.compile(r"/(\d+)/?$")
_YEAR_TITLE_RE = re.compile(r"^\s*(\d{4})\s*-\s*(.+)$")
_ALBUM_HEADER_RE = re.compile(r"^(.*?)\s+—\s+(.*?)\s*\((\d{4})\)\s*$")
_TRACK_RE = re.compile(
    r'\{\s*title:\s*"((?:[^"\\]|\\.)*)"\s*,.*?mp3:\s*"((?:[^"\\]|\\.)*)"\s*\}',
    re.S,
)


class SiteError(Exception):
    pass


@dataclass
class Band:
    id: int
    name: str
    genre: str = ""

    @property
    def image(self) -> str:
        return f"{BASE_URL}/upload/images/bands/{self.id}.jpg"


@dataclass
class Genre:
    id: int
    name: str


@dataclass
class AlbumRef:
    id: int
    title: str
    year: str = ""

    @property
    def cover(self) -> str:
        return album_cover(self.id)


@dataclass
class Track:
    number: int
    title: str
    url: str


@dataclass
class Album:
    id: int
    title: str
    year: str
    band_id: Optional[int]
    band_name: str
    tracks: list[Track] = field(default_factory=list)

    @property
    def cover(self) -> str:
        return album_cover(self.id)


@dataclass
class BandDetails:
    band: Band
    albums: list[AlbumRef]


@dataclass
class BandsPage:
    bands: list[Band]
    page: int
    pages: int


def album_cover(album_id: int) -> str:
    return f"{BASE_URL}/upload/images/albums/{album_id}.jpg"


def _normalize_mp3_url(raw: str) -> str:
    """Site links are `http://`, half-encoded; make them clean https URLs."""
    url = raw.replace("\\/", "/").replace('\\"', '"')
    url = re.sub(r"^http://", "https://", url)
    if url.startswith("/"):
        url = BASE_URL + url
    scheme, rest = url.split("://", 1)
    host, _, path = rest.partition("/")
    return f"{scheme}://{host}/" + quote(unquote(path), safe="/")


def _unescape_js(s: str) -> str:
    return re.sub(r"\\(.)", r"\1", s)


class RocknationClient:
    def __init__(self, timeout: float = 20.0):
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
        self._genres: Optional[list[Genre]] = None

    async def close(self):
        await self._client.aclose()

    async def _get(self, path: str) -> BeautifulSoup:
        try:
            r = await self._client.get(path)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise SiteError(f"Не удалось загрузить {path}: {e}") from e
        return BeautifulSoup(r.text, "html.parser")

    # ---- catalog ----

    async def genres(self) -> list[Genre]:
        if self._genres is None:
            soup = await self._get("/mp3/")
            self._genres = _parse_genres(soup)
        return self._genres

    async def bands(self, page: int = 1) -> BandsPage:
        return await self._bands_page("/mp3", page)

    async def bands_by_letter(self, letter: str, page: int = 1) -> BandsPage:
        return await self._bands_page(f"/mp3/letter-{letter.lower()}", page)

    async def bands_by_genre(self, genre_id: int, page: int = 1) -> BandsPage:
        return await self._bands_page(f"/mp3/genre-{genre_id}", page)

    async def _bands_page(self, prefix: str, page: int) -> BandsPage:
        path = f"{prefix}/" if page <= 1 else f"{prefix}/{page}"
        soup = await self._get(path)
        # The current page is not a link, so on the last page it is missed.
        pages = max(page, _parse_pages(soup))
        return BandsPage(_parse_bands_table(soup), page, pages)

    async def search(self, text: str) -> list[Band]:
        try:
            r = await self._client.post(
                "/mp3/searchresult/",
                data={"text_mp3": text, "enter_mp3": "Search"},
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise SiteError(f"Ошибка поиска: {e}") from e
        return _parse_bands_table(BeautifulSoup(r.text, "html.parser"))

    # ---- band / album ----

    async def band(self, band_id: int) -> BandDetails:
        soup = await self._get(f"/mp3/band-{band_id}")
        name = _parse_band_name(soup) or f"Band {band_id}"
        albums = _parse_albums(soup)
        pages = _parse_pages(soup)
        for page in range(2, pages + 1):
            albums += _parse_albums(await self._get(f"/mp3/band-{band_id}/{page}"))
        return BandDetails(Band(band_id, name), albums)

    async def album(self, album_id: int) -> Album:
        soup = await self._get(f"/mp3/album-{album_id}")
        band_id, band_name, title = None, "", ""
        brad = soup.select_one("div.brad")
        if brad:
            for a in brad.find_all("a"):
                m = _BAND_RE.search(a.get("href", ""))
                if m:
                    band_id = int(m.group(1))
                    band_name = a.get_text(strip=True)
            span = brad.find("span")
            if span:
                title = span.get_text(strip=True)

        year = ""
        for p in soup.select("#mp3 p"):
            m = _ALBUM_HEADER_RE.match(p.get_text(" ", strip=True))
            if m:
                band_name = band_name or m.group(1)
                title = title or m.group(2)
                year = m.group(3)
                break

        tracks = []
        for script in soup.find_all("script"):
            text = script.string or ""
            if "jPlayerPlaylist" not in text:
                continue
            for i, m in enumerate(_TRACK_RE.finditer(text), start=1):
                tracks.append(
                    Track(i, _unescape_js(m.group(1)), _normalize_mp3_url(m.group(2)))
                )
        return Album(album_id, title, year, band_id, band_name, tracks)


def _parse_genres(soup: BeautifulSoup) -> list[Genre]:
    genres = []
    for a in soup.select("#genre a"):
        m = _GENRE_RE.search(a.get("href", ""))
        if m:
            genres.append(Genre(int(m.group(1)), a.get_text(strip=True)))
    return genres


def _parse_bands_table(soup: BeautifulSoup) -> list[Band]:
    bands = []
    for row in soup.select("table.table-bands tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        a = cells[0].find("a")
        m = _BAND_RE.search(a.get("href", "")) if a else None
        if not m:
            continue
        genre = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        bands.append(Band(int(m.group(1)), a.get_text(strip=True), genre))
    return bands


def _parse_pages(soup: BeautifulSoup) -> int:
    pages = 1
    for a in soup.select("ul.pagination a"):
        m = _PAGE_RE.search(a.get("href", ""))
        if m:
            pages = max(pages, int(m.group(1)))
    return pages


def _parse_band_name(soup: BeautifulSoup) -> str:
    brad = soup.select_one("div.brad")
    if brad:
        span = brad.find("span")
        if span:
            return span.get_text(strip=True)
        links = brad.find_all("a")
        if len(links) > 1:
            return links[-1].get_text(strip=True)
    title = soup.find("title")
    return title.get_text(strip=True) if title else ""


def _parse_albums(soup: BeautifulSoup) -> list[AlbumRef]:
    albums = []
    for a in soup.select("#clips ol.list a"):
        m = _ALBUM_RE.search(a.get("href", ""))
        if not m:
            continue
        text = a.get_text(strip=True)
        ym = _YEAR_TITLE_RE.match(text)
        if ym:
            albums.append(AlbumRef(int(m.group(1)), ym.group(2), ym.group(1)))
        else:
            albums.append(AlbumRef(int(m.group(1)), text))
    return albums


def absolute_url(path: str) -> str:
    return urljoin(BASE_URL + "/", path)
