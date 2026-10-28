"""Menu de consultas e testes de CAPTCHA no terminal."""

import argparse


def executar(opcao: str, objeto: str, navegador: str, manter_aberto: bool, cnpj: str = "", parte: str = "") -> int:
    if opcao in {"5", "stj"}:
        from consultar_stj import main
        return main(["--parte", parte, "--navegador", navegador])
    if opcao in {"4", "trf3"}:
        from consultar_trf3 import main
        return main(["--cnpj", cnpj, "--navegador", navegador])
    if opcao in {"1", "v1"}:
        from rastreamento_correios import main
        argumentos = ["--navegador", navegador]
        if objeto:
            argumentos.extend(["--objeto", objeto])
        if manter_aberto:
            argumentos.append("--manter-aberto")
        return main(argumentos)
    if opcao in {"3", "cloudflare", "tjsp"}:
        from testar_cloudflare import main
        return main(["--navegador", navegador])
    from testar_recaptcha import main
    return main(["--automatico", "--navegador", navegador])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tipo", choices=("1", "2", "3", "4", "5", "v1", "v2", "cloudflare", "tjsp", "trf3", "stj"))
    parser.add_argument("--objeto", default="")
    parser.add_argument("--cnpj", default="")
    parser.add_argument("--parte", default="")
    parser.add_argument("--navegador", choices=("chrome", "msedge", "chromium"), default="chrome")
    args = parser.parse_args(argv)
    if args.tipo:
        if args.tipo in {"4", "trf3"} and not args.cnpj:
            parser.error("A opção TRF3 exige --cnpj.")
        if args.tipo in {"5", "stj"} and not args.parte:
            parser.error("A opção STJ exige --parte com o nome da parte.")
        return executar(args.tipo, args.objeto, args.navegador, False, args.cnpj, args.parte)
    while True:
        print("\nCONSULTAS E CAPTCHA")
        print("1 - Correios: CAPTCHA de letras e rastreamento")
        print("2 - Google: reCAPTCHA v2 automático")
        print("3 - TJSP: testar Cloudflare Turnstile (sem número de processo)")
        print("4 - TRF3: consulta pública por CNPJ")
        print("5 - STJ: consulta pública pelo nome da parte")
        print("0 - Sair")
        try:
            escolha = input("Digite 1, 2, 3, 4 ou 5: ").strip().lower()
            if escolha in {"0", "sair"}:
                return 0
            if escolha not in {"1", "2", "3", "4", "5", "v1", "v2", "cloudflare", "tjsp", "trf3", "stj"}:
                print("Escolha 1, 2, 3, 4, 5 ou 0.")
                continue
            objeto = ""
            if escolha in {"1", "v1"}:
                objeto = input("Código de rastreamento (ENTER para somente ler o CAPTCHA): ").strip()
            cnpj = input("CNPJ da empresa: ").strip() if escolha in {"4", "trf3"} else ""
            if escolha in {"4", "trf3"}:
                from consultar_trf3 import normalizar_cnpj
                try:
                    cnpj = normalizar_cnpj(cnpj)
                except ValueError as exc:
                    print(str(exc))
                    continue
            parte = input("Nome da parte (o STJ não pesquisa por CPF/CNPJ): ").strip() if escolha in {"5", "stj"} else ""
            if escolha in {"5", "stj"}:
                from consultar_stj import normalizar_nome
                try:
                    parte = normalizar_nome(parte)
                except ValueError as exc:
                    print(str(exc))
                    continue
            executar(escolha, objeto, args.navegador, not objeto and escolha in {"1", "v1"}, cnpj, parte)
            input("\nPressione ENTER para voltar ao menu. ")
        except (KeyboardInterrupt, EOFError):
            print("\nFerramenta encerrada.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
