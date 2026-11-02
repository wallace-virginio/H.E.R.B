# Ferramentas e segurança

## Níveis

| Nível | Exemplos | Comportamento |
|------:|----------|---------------|
| 1 | abrir app, URL, system_info | executa direto |
| 2 | criar/mover arquivos, digitar | pede confirmação |
| 3 | excluir arquivos | confirmação explícita |

Shell arbitrário (`run_shell`, `cmd`, `powershell`) é **bloqueado**.

## Adicionar uma ferramenta

1. Implemente a função em `app/automation/tools.py` (ou módulo novo)
2. Registre em `register_default_tools` com `AuthLevel` adequado
3. Documente parâmetros no `parameters={...}`
4. Adicione teste em `tests/test_tools.py`

Exemplo:

```python
registry.register(
    "open_downloads",
    "Abre a pasta Downloads do usuário.",
    AuthLevel.SIMPLE,
    lambda: open_path(str(Path.home() / "Downloads")),
)
```

## Parada de emergência

- Botão **STOP** na interface
- Comando: `parada de emergência`
- Libera com: `liberar emergência`
