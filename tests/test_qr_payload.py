import unittest

from services.qrcode_service import qr_payload


class QrPayloadTests(unittest.TestCase):
    def test_measurements_are_next_to_description_before_seal(self) -> None:
        data = {
            "descricao": "TUBO SULAMERICANA",
            "medidas": "1650MM X 3X2,5MM",
            "lote_controle": "123",
            "quantidade": "300",
        }
        payload = qr_payload(data, "AZ0000084688")
        self.assertIn("(D)TUBO SULAMERICANA 1650MM X 3X2,5MM(S)123", payload)
        self.assertNotIn("(M)", payload)

    def test_empty_measurements_do_not_add_separator(self) -> None:
        for measurements in (None, "", "   "):
            with self.subTest(measurements=measurements):
                payload = qr_payload({"descricao": "TUBO", "medidas": measurements,
                                      "quantidade": "300"}, "AZ0000084688")
                self.assertIn("(D)TUBO(S)", payload)

    def test_matches_production_reader_example(self) -> None:
        data = {
            "tipo": "MP",
            "produto_codigo": "0112000497",
            "descricao": "TUBO SULAMERICANA-1650MM X 3X2,5MM-CAPA BRANCA - 10 ANOS",
            "medidas": "1650MM X 3X2,5MM",
            "lote_controle": "123",
            "quantidade": "300",
            "dpd": "",
            "unidade": "UN",
            "lote_base": "",
        }
        self.assertEqual(
            qr_payload(data, "AZ0000084688", "04"),
            "(E)04(T)MP(P)0112000497"
            "(D)TUBO SULAMERICANA-1650MM X 3X2,5MM-CAPA BRANCA - 10 ANOS"
            "(S)123(Q)300000(Y)(I)AZ0000084688(U)UN(L)",
        )


if __name__ == "__main__":
    unittest.main()
