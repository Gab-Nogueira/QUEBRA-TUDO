"""Menu de consultas e testes de CAPTCHA no terminal."""

import argparse


def executar(opcao: str, objeto: str, navegador: str, manter_aberto: bool) -> int:
    if opcao in {"1", "v1"}:
        from rastreamento_correios import main
        argumentos = ["--navegador", navegador]
        if objeto:
            argumentos.extend(["--objeto", objeto])
        if manter_aberto:
            argumentos.append("--manter-aberto")
        return main(argumentos)
    from testar_recaptcha import main
    return main(["--automatico", "--navegador", navegador])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tipo", choices=("1", "2", "v1", "v2"))
    parser.add_argument("--objeto", default="")
    parser.add_argument("--navegador", choices=("chrome", "msedge", "chromium"), default="chrome")
    args = parser.parse_args(argv)
    if args.tipo:
        return executar(args.tipo, args.objeto, args.navegador, False)
    while True:
        print("\nCONSULTAS E CAPTCHA")
        print("1 - Correios: CAPTCHA de letras e rastreamento")
        print("2 - Google: reCAPTCHA v2 automático")
        print("0 - Sair")
        try:
            escolha = input("Digite 1 ou 2 (também aceita v1/v2): ").strip().lower()
            if escolha in {"0", "sair"}:
                return 0
            if escolha not in {"1", "2", "v1", "v2"}:
                print("Escolha 1, 2 ou 0.")
                continue
            objeto = ""
            if escolha in {"1", "v1"}:
                objeto = input("Código de rastreamento (ENTER para somente ler o CAPTCHA): ").strip()
            executar(escolha, objeto, args.navegador, not objeto and escolha in {"1", "v1"})
            input("\nPressione ENTER para voltar ao menu. ")
        except (KeyboardInterrupt, EOFError):
            print("\nFerramenta encerrada.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
