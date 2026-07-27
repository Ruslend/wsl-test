import tempfile
import unittest
from pathlib import Path
from database import TicketRepository

class TicketRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir=tempfile.TemporaryDirectory()
        self.repo=TicketRepository(Path(self.temp_dir.name)/'test.db')
        self.repo.initialize(seed=False)
    def tearDown(self): self.temp_dir.cleanup()
    def test_create_and_update(self):
        ticket=self.repo.create_ticket({'title':'Настроить VPN','department':'IT','requester':'Руслан','priority':'high'})
        self.assertEqual(ticket['status'],'new')
        updated=self.repo.update_status(ticket['id'],'done')
        self.assertEqual(updated['status'],'done')
        self.assertEqual(self.repo.stats()['done'],1)
    def test_validation(self):
        with self.assertRaises(ValueError): self.repo.create_ticket({'title':'','department':'IT','requester':'A','priority':'medium'})

if __name__=='__main__': unittest.main()
