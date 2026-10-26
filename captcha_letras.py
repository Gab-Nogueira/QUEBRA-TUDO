"""Leitura local de CAPTCHA alfanumérico com modelos OCR abertos."""

from collections import Counter
from io import BytesIO
import re


class LeitorLetras:
    def __init__(self):
        print("Carregando leitor local de letras...", flush=True)
        try:
            import ddddocr
        except ImportError as exc:
            raise RuntimeError("Execute INSTALAR_AUTOMATICO.cmd para instalar o leitor de letras.") from exc
        self.modelos = [("padrao", ddddocr.DdddOcr(show_ad=False)),
                        ("beta", ddddocr.DdddOcr(show_ad=False, beta=True))]

    def ler(self, imagem: bytes) -> dict:
        from PIL import Image
        original = Image.open(BytesIO(imagem)).convert("L")
        # O texto cinza dos Correios é mais claro que as linhas que o atravessam.
        limpa = original.point(lambda pixel: 255 if pixel < 125 else pixel)
        buffer = BytesIO()
        limpa.save(buffer, format="PNG")
        leituras = []
        for variante, conteudo in (("original", imagem), ("sem_linhas_escuras", buffer.getvalue())):
            for nome, modelo in self.modelos:
                texto = modelo.classification(conteudo).strip()
                if re.fullmatch(r"[A-Za-z0-9]{3,8}", texto):
                    leituras.append({"texto": texto, "modelo": nome, "variante": variante})
        if not leituras:
            raise RuntimeError("O leitor não reconheceu um código alfanumérico na imagem.")
        contagem = Counter(item["texto"] for item in leituras)
        candidatos = sorted(contagem, key=lambda texto: -contagem[texto])
        return {"texto": candidatos[0], "alternativas": candidatos[1:], "leituras": leituras,
                "leituras_concordantes": len(candidatos) == 1}
