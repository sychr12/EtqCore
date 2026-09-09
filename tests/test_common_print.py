import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import app
from models import database


class CommonPrintTests(unittest.TestCase):
    def test_common_print_generates_unique_qrs_and_history_without_raw_print(self):
        with TemporaryDirectory() as temp:
            with patch.object(database, 'DATA_DIR', Path(temp)), patch.object(database, 'DB_PATH', Path(temp) / 'test.db'):
                database.init_db()
                with patch('services.geracao.raw_print') as raw, patch('services.geracao.resolve_printer') as resolve:
                    client = app.test_client()
                    response = client.post('/api/gerar', json={
                        'destino': 'impressora_comum', 'quantidade_etiquetas': 2,
                        'produto_codigo': '123', 'descricao': 'ETIQUETA TESTE',
                        'lote_controle': 'TESTE', 'quantidade': '10', 'unidade': 'UN',
                        'observacao': 'Somente na etiqueta',
                    })
                    self.assertEqual(response.status_code, 200)
                    labels = response.get_json()['etiquetas']
                    self.assertEqual(len(labels), 2)
                    self.assertNotEqual(labels[0]['identificador'], labels[1]['identificador'])
                    self.assertNotEqual(labels[0]['qr_svg'], labels[1]['qr_svg'])
                    self.assertTrue(all('<svg' in row['qr_svg'] for row in labels))
                    history = client.get('/api/historico').get_json()
                    self.assertEqual(len(history), 2)
                    self.assertTrue(all(row['destino'] == 'impressora_comum' for row in history))
                    raw.assert_not_called()
                    resolve.assert_not_called()
