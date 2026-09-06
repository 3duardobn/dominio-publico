"""Fixtures OAI-PMH mínimas para testar o harvester offline."""
OAI_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"
         xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
  <ListRecords>
    <record>
      <header><identifier>oai:teste:1</identifier><datestamp>2024-01-01</datestamp></header>
      <metadata>
        <oai_dc:dc>
          <dc:title>Obra de Teste</dc:title>
          <dc:creator>Autor Teste</dc:creator>
          <dc:date>2024</dc:date>
          <dc:type>text</dc:type>
        </oai_dc:dc>
      </metadata>
    </record>
    <record>
      <header><identifier>oai:teste:2</identifier><datestamp>2024-01-02</datestamp></header>
      <metadata>
        <oai_dc:dc>
          <dc:title>Segunda Obra</dc:title>
          <dc:creator>Outro Autor</dc:creator>
        </oai_dc:dc>
      </metadata>
    </record>
    <resumptionToken/>
  </ListRecords>
</OAI-PMH>"""

DSPACE_ITEM_SAMPLE = {
    "uuid": "abc-123",
    "metadata": {
        "dc.title": [{"value": "Tese de Teste"}],
        "dc.contributor.author": [{"value": "Maria Silva"}],
        "dc.date.issued": [{"value": "2023-05-01"}],
        "dc.type": [{"value": "info:eu-repo/semantics/masterThesis"}],
        "dc.identifier.uri": [{"value": "https://arca.fiocruz.br/handle/icict/999"}],
        "dc.subject": [{"value": "Saúde pública"}],
        "dc.description.abstract": [{"value": "Resumo da tese."}],
    },
}
