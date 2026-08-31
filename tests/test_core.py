from __future__ import annotations

import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import app
from models import database
from services.contador import counter_token
from services.impressao import recommended_zebra
from services.texto import quantity_x1000
from services.validacao import validate_label, validate_settings


VALID_LABEL = {
    "tipo": "CAPA",
    "produto_codigo": "2000000444",
    "descricao": "Produto teste",
    "lote_controle": "BC",
    "quantidade": "95,5",
    "unidade": "pcs",
}


class CounterTests(unittest.TestCase):
    def test_numeric_and_alphanumeric_boundaries(self) -> None:
        self.assertEqual(counter_token(1), "0000000001")
        self.assertEqual(counter_token(9_999_999_999), "9999999999")
        self.assertEqual(counter_token(10_000_000_000), "A000000000")
        self.assertEqual(counter_token(10_999_999_999), "A999999999")
        self.assertEqual(counter_token(11_000_000_000), "B000000000")

    def test_counter_rejects_non_positive_values(self) -> None:
        with self.assertRaises(ValueError):
            counter_token(0)


class PrinterTests(unittest.TestCase):
    def test_zd220_is_preferred(self) -> None:
        printers = ["Microsoft Print to PDF", "ZDesigner GK420d", "ZDesigner ZD220-203dpi ZPL"]
        self.assertEqual(recommended_zebra(printers), "ZDesigner ZD220-203dpi ZPL")


class ValidationTests(unittest.TestCase):
    def test_quantity_formats(self) -> None:
        self.assertEqual(quantity_x1000("95,5"), "95500")
        self.assertEqual(quantity_x1000("1.234,5"), "1234500")

    def test_quantity_rejects_non_positive_and_non_finite(self) -> None:
        for value in ("0", "-1", "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                quantity_x1000(value)

    def test_label_is_cleaned_and_validated(self) -> None:
        result = validate_label({**VALID_LABEL, "descricao": "Produto^\nTeste"})
        self.assertEqual(result["descricao"], "Produto  Teste")

    def test_tipo_is_optional(self) -> None:
        result = validate_label({**VALID_LABEL, "tipo": ""})
        self.assertEqual(result["tipo"], "")

    def test_text_is_normalized_for_utf8_zpl(self) -> None:
        result = validate_label({**VALID_LABEL, "descricao": "AÇA\u0303O"})
        self.assertEqual(result["descricao"], "AÇÃO")

    def test_settings_reject_non_finite_dimensions(self) -> None:
        with self.assertRaises(ValueError):
                validate_settings({"largura_mm": "nan", "comprimento_mm": 60, "dpi": 203, "filial": "04"})

    def test_settings_enforce_zd220_profile(self) -> None:
        with self.assertRaises(ValueError):
            validate_settings({"largura_mm": 100, "comprimento_mm": 60, "dpi": 300, "filial": "04"})
        with self.assertRaises(ValueError):
            validate_settings({"largura_mm": 105, "comprimento_mm": 60, "dpi": 203, "filial": "04"})


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_invalid_json_is_a_client_error(self) -> None:
        response = self.client.post("/api/gerar", data="not-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_destination_is_rejected_before_counter_reservation(self) -> None:
        response = self.client.post("/api/gerar", json={**VALID_LABEL, "destino": "arquivo-arbitrario"})
        self.assertEqual(response.status_code, 400)

    def test_qr_payload_has_a_size_limit(self) -> None:
        response = self.client.post("/api/qr.svg", data="x" * 4097)
        self.assertEqual(response.status_code, 400)

    def test_missing_printer_fails_before_reserving_counter(self) -> None:
        before = self.client.get("/api/estado").get_json()["proximo_numero"]
        with patch("services.geracao.resolve_printer", side_effect=RuntimeError("Zebra não encontrada")):
            response = self.client.post(
                "/api/gerar",
                json={**VALID_LABEL, "destino": "imprimir", "quantidade_etiquetas": 1},
            )
        after = self.client.get("/api/estado").get_json()["proximo_numero"]
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.get_json()["consumido"])
        self.assertEqual(after, before)

    def test_preview_reports_physical_print_dimensions(self) -> None:
        response = self.client.post("/api/preview", json=VALID_LABEL)
        self.assertEqual(response.status_code, 200)
        profile = response.get_json()["impressao"]
        self.assertEqual(profile["dpi"], 203)
        self.assertEqual(profile["largura_dots"], 800)
        self.assertEqual(profile["comprimento_dots"], 480)

    def test_preview_and_zpl_allow_empty_tipo(self) -> None:
        label = {**VALID_LABEL, "tipo": ""}
        response = self.client.post("/api/preview", json=label)
        self.assertEqual(response.status_code, 200)
        preview = response.get_json()
        self.assertIn("(T)(P)2000000444", preview["qr"])

        from services.zpl import make_zpl

        zpl = make_zpl(
            validate_label(label),
            1,
            "TB0000000001",
            preview["qr"],
            {
                "largura_mm": "100",
                "comprimento_mm": "60",
                "dpi": "203",
                "velocidade_ips": "3",
                "tonalidade": "10",
                "deslocamento_x_mm": "0",
                "deslocamento_y_mm": "0",
            },
        )
        self.assertIn("^XA", zpl)
        self.assertIn("^XZ", zpl)

    def test_generation_reserves_unique_counters_and_returns_zpl(self) -> None:
        with TemporaryDirectory() as directory:
            old_data_dir, old_db_path, old_backup_dir = (
                database.DATA_DIR,
                database.DB_PATH,
                database.BACKUP_DIR,
            )
            try:
                database.DATA_DIR = Path(directory)
                database.DB_PATH = Path(directory) / "test.db"
                database.BACKUP_DIR = Path(directory) / "backups"
                database.init_db()

                response = self.client.post(
                    "/api/gerar",
                    json={
                        **VALID_LABEL,
                        "descricao": "TUBETE AÇÃO ÇÃ",
                        "destino": "download",
                        "quantidade_etiquetas": 2,
                    },
                )
                payload = response.get_json()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(payload["quantidade"], 2)
                self.assertEqual(payload["identificador"], "TB0000000001")
                self.assertEqual(payload["ultimo_identificador"], "TB0000000002")
                self.assertEqual(payload["zpl"].count("^XA"), 2)
                self.assertIn("^CI28", payload["zpl"])
                self.assertNotIn("^CI27", payload["zpl"])
                self.assertIn("^MNA", payload["zpl"])
                self.assertIn("^PR3", payload["zpl"])
                self.assertIn("~SD10", payload["zpl"])
                self.assertIn("^PW800", payload["zpl"])
                self.assertIn("^LL480", payload["zpl"])
                self.assertIn("^BQN,2,4", payload["zpl"])
                self.assertIn("TUBETE AÇÃO ÇÃ", payload["zpl"])
                self.assertIn("^GFA", payload["zpl"])
                # Coluna TIPO/LOTE: bloco preto, divisor branco e textos reversos.
                self.assertIn("^FO232,28^GB88,204,88,B,0^FS", payload["zpl"])
                self.assertIn("^FO232,130^GB88,2,2,W,0^FS", payload["zpl"])
                self.assertIn("^FO232,61^FR^A0N,36,36^FB88,1,0,C,0^FDCAPA^FS", payload["zpl"])
                self.assertIn("^FO232,154^FR^A0N,54,54^FB88,1,0,C,0^FDBC^FS", payload["zpl"])
                # Separadores das quatro faixas do novo layout com QR maior.
                self.assertIn("^FO28,232^GB672,4,4,B,0^FS", payload["zpl"])
                self.assertIn("^FO28,292^GB672,4,4,B,0^FS", payload["zpl"])
                self.assertIn("^FO28,368^GB672,4,4,B,0^FS", payload["zpl"])

                with closing(database.db()) as connection:
                    next_counter = connection.execute(
                        "SELECT valor FROM config WHERE chave='proximo_contador'"
                    ).fetchone()[0]
                    label_count = connection.execute("SELECT COUNT(*) FROM etiquetas").fetchone()[0]
                self.assertEqual(next_counter, "3")
                self.assertEqual(label_count, 2)
            finally:
                database.DATA_DIR = old_data_dir
                database.DB_PATH = old_db_path
                database.BACKUP_DIR = old_backup_dir


if __name__ == "__main__":
    unittest.main()
