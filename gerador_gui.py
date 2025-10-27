import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import json
from pathlib import Path
from crypto_utils import encrypt_text, decrypt_text
import os

BASE_DIR = Path(__file__).parent
is_busy = False  # trava global

# ========= Funções utilitárias =========
def limpar_unicode(texto: str) -> str:
    """Remove caracteres fora do intervalo CP1252 (ex.: emojis)."""
    if not isinstance(texto, str):
        return ""
    return ''.join(ch for ch in texto if ord(ch) < 128 or 160 <= ord(ch) <= 255)

def safe_msg(texto: str) -> str:
    """Garante que o texto é exibível em pop-ups no Windows."""
    try:
        return texto.encode("cp1252", errors="ignore").decode("cp1252", errors="ignore")
    except Exception:
        return limpar_unicode(texto)

def atualizar_status(mensagem, cor="black"):
    """Atualiza a mensagem na barra de status imediatamente."""
    status_label.config(text=mensagem, fg=cor)
    status_label.update_idletasks()

def listar_agendamentos():
    """Lista todos os arquivos .json do diretório."""
    return [f.stem for f in BASE_DIR.glob("*.json")]

def set_busy(busy: bool):
    """Habilita/Desabilita todos os controles enquanto uma ação roda."""
    global is_busy
    is_busy = busy
    state = tk.DISABLED if busy else tk.NORMAL

    # Campos de entrada
    for w in inputs_to_toggle:
        try:
            w.configure(state=state)
        except tk.TclError:
            pass

    # Botões
    for b in buttons_to_toggle:
        try:
            b.configure(state=state)
        except tk.TclError:
            pass

    # Cursor
    root.config(cursor="watch" if busy else "")
    root.update_idletasks()

def bloquear_se_ocupado():
    """Evita reentrância em ações."""
    if is_busy:
        atualizar_status("Uma ação já está em andamento. Aguarde…", "red")
        return True
    return False

def carregar_agendamento(event=None):
    if bloquear_se_ocupado():
        return
    nome = combo_agendamento.get().strip()
    if not nome:
        return
    config_path = BASE_DIR / f"{nome}.json"
    if not config_path.exists():
        atualizar_status("Arquivo de configuração não encontrado.", "red")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # ⚙️ Preenche todos os campos ANTES de travar a interface
        combo_agendamento.set(cfg.get("NOME_AGENDAMENTO", nome))
        entry_usuario.delete(0, tk.END); entry_usuario.insert(0, cfg.get("USUARIO", ""))
        entry_senha.delete(0, tk.END);   entry_senha.insert(0, decrypt_text(cfg.get("SENHA", "")))
        entry_tenant.delete(0, tk.END);  entry_tenant.insert(0, cfg.get("TENANT_GUID", ""))
        entry_ambiente.delete(0, tk.END);entry_ambiente.insert(0, cfg.get("AMBIENTE", ""))
        entry_empresa.delete(0, tk.END); entry_empresa.insert(0, cfg.get("EMPRESA", ""))
        entry_nome.delete(0, tk.END);    entry_nome.insert(0, cfg.get("NOME_RELATORIO", ""))
        entry_pasta.delete(0, tk.END);   entry_pasta.insert(0, cfg.get("PASTA_DESTINO", ""))
        entry_hora.delete(0, tk.END);    entry_hora.insert(0, cfg.get("HORA", ""))
        combo_periodicidade.set(cfg.get("PERIODICIDADE", ""))

        atualizar_status(f"[OK] Agendamento '{nome}' carregado.", "green")
        root.update()

        # Agora sim: trava temporariamente enquanto mostra o pop-up
        set_busy(True)
        messagebox.showinfo("Agendamento carregado", f"Agendamento '{nome}' carregado com sucesso!")
    except Exception as e:
        atualizar_status(f"[ERRO] Falha ao carregar: {e}", "red")
    finally:
        set_busy(False)


def salvar_config(nome_agendamento):
    dados = {
        "USUARIO": entry_usuario.get(),
        "SENHA": encrypt_text(entry_senha.get()),
        "TENANT_GUID": entry_tenant.get(),
        "AMBIENTE": entry_ambiente.get(),
        "EMPRESA": entry_empresa.get(),
        "NOME_RELATORIO": entry_nome.get(),
        "PASTA_DESTINO": entry_pasta.get(),
        "HORA": entry_hora.get(),
        "PERIODICIDADE": combo_periodicidade.get().upper(),
        "NOME_AGENDAMENTO": nome_agendamento
    }
    caminho = BASE_DIR / f"{nome_agendamento}.json"
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)
    return caminho

def agendar_tarefa():
    if bloquear_se_ocupado():
        return
    nome_agendamento = combo_agendamento.get().strip()
    if not nome_agendamento:
        messagebox.showerror("Erro", "Informe um nome para o agendamento.")
        atualizar_status("[ERRO] Nome do agendamento obrigatório.", "red")
        return

    set_busy(True)
    try:
        hora = entry_hora.get().strip()
        periodicidade = combo_periodicidade.get().upper()
        config_path = salvar_config(nome_agendamento)
        script_path = BASE_DIR / "gerar_relatorio_lg.py"

        if not script_path.exists():
            atualizar_status("[ERRO] Script principal não encontrado.", "red")
            root.update()
            messagebox.showerror("Erro", f"Script principal não encontrado:\n{script_path}")
            return

        sc_map = {"DIARIO": "DAILY", "SEMANAL": "WEEKLY", "MENSAL": "MONTHLY"}
        sc_val = sc_map.get(periodicidade, "DAILY")

        comando = f'schtasks /Create /TN "{nome_agendamento}" /TR "python \\"{script_path}\\"" /SC {sc_val} /ST {hora} /F'
        resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)

        if resultado.returncode == 0:
            atualizar_status(f"[OK] Tarefa '{nome_agendamento}' criada.", "green")
            root.update()
            messagebox.showinfo(
                "Sucesso",
                f"Tarefa '{nome_agendamento}' agendada ({periodicidade.lower()}) para {hora}!\n"
                f"Configurações salvas em:\n{config_path}"
            )
            atualizar_lista_agendamentos()
        else:
            atualizar_status("[ERRO] Falha ao criar tarefa.", "red")
            root.update()
            messagebox.showerror("Erro", f"Falha ao criar tarefa:\n{resultado.stderr}")
    except Exception as e:
        atualizar_status(f"[ERRO] {e}", "red")
        root.update()
        messagebox.showerror("Erro", str(e))
    finally:
        set_busy(False)

def apagar_tarefa():
    if bloquear_se_ocupado():
        return
    nome_agendamento = combo_agendamento.get().strip()
    if not nome_agendamento:
        atualizar_status("[ERRO] Nenhum agendamento selecionado.", "red")
        root.update()
        messagebox.showerror("Erro", "Selecione um agendamento para apagar.")
        return

    set_busy(True)
    try:
        subprocess.run(f'schtasks /Delete /TN "{nome_agendamento}" /F', shell=True, capture_output=True)

        json_path = BASE_DIR / f"{nome_agendamento}.json"
        if json_path.exists():
            json_path.unlink()

        atualizar_lista_agendamentos()
        atualizar_status(f"[REMOVIDO] Agendamento '{nome_agendamento}' excluído.", "green")
        root.update()
        messagebox.showinfo("Sucesso", f"Agendamento '{nome_agendamento}' removido com sucesso!")
    except Exception as e:
        atualizar_status(f"[ERRO] {e}", "red")
        root.update()
        messagebox.showerror("Erro", str(e))
    finally:
        set_busy(False)

def testar_execucao():
    if bloquear_se_ocupado():
        return
    nome_agendamento = combo_agendamento.get().strip()
    if not nome_agendamento:
        atualizar_status("[ERRO] Nenhum agendamento selecionado para teste.", "red")
        messagebox.showerror("Erro", "Selecione ou crie um agendamento para testar.")
        return

    config_path = BASE_DIR / f"{nome_agendamento}.json"
    if not config_path.exists():
        atualizar_status("[ERRO] Arquivo JSON não encontrado.", "red")
        messagebox.showerror("Erro", f"O arquivo {nome_agendamento}.json não foi encontrado.")
        return

    script_path = BASE_DIR / "gerar_relatorio_lg.py"
    if not script_path.exists():
        atualizar_status("[ERRO] Script principal não encontrado.", "red")
        messagebox.showerror("Erro", f"O script principal não foi encontrado:\n{script_path}")
        return

    set_busy(True)
    try:
        atualizar_status(f"[EXECUTANDO] Relatório '{nome_agendamento}'...", "blue")
        root.update()
        messagebox.showinfo("Execução iniciada", f"Rodando o relatório '{nome_agendamento}'...\nAguarde a conclusão.")

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"

        resultado = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            env=env
        )

        saida = resultado.stdout or ""
        erro  = resultado.stderr or ""

        if resultado.returncode == 0:
            saida_limpa = safe_msg(saida)
            atualizar_status("[OK] Execução concluída com sucesso.", "green")
            root.update()
            messagebox.showinfo("Teste concluído", safe_msg("Execução finalizada com sucesso!\n\nSaída:\n" + saida_limpa[-400:]))
        else:
            erro_limpo = safe_msg(erro)
            atualizar_status("[ERRO] Falha durante a execução.", "red")
            root.update()
            messagebox.showerror("Erro na execução", safe_msg("Erro ao executar:\n" + erro_limpo[-400:]))
    except Exception as e:
        atualizar_status(f"[ERRO] {e}", "red")
        messagebox.showerror("Erro", safe_msg(str(e)))
    finally:
        set_busy(False)


def escolher_pasta():
    if bloquear_se_ocupado():
        return
    pasta = filedialog.askdirectory()
    if pasta:
        entry_pasta.delete(0, tk.END)
        entry_pasta.insert(0, pasta)
        atualizar_status(f"Pasta selecionada: {pasta}", "blue")

def atualizar_lista_agendamentos():
    valores = listar_agendamentos()
    combo_agendamento["values"] = valores
    atualizar_status("Aguardando ação...")

# ========= INTERFACE =========
root = tk.Tk()
root.title("Agendador Automático - Relatórios LG (Multi-Relatório)")
root.geometry("600x760")

tk.Label(root, text="Selecione ou crie um agendamento:").pack(pady=5)
frame_ag = tk.Frame(root); frame_ag.pack()

combo_agendamento = ttk.Combobox(frame_ag, width=35, values=listar_agendamentos())
combo_agendamento.pack(side=tk.LEFT, padx=5)
combo_agendamento.bind("<<ComboboxSelected>>", carregar_agendamento)
btn_carregar = tk.Button(frame_ag, text="Carregar", command=carregar_agendamento, bg="#0078D7", fg="white")
btn_carregar.pack(side=tk.LEFT, padx=5)

# Campos principais
tk.Label(root, text="Usuário:").pack()
entry_usuario = tk.Entry(root, width=50); entry_usuario.pack()

tk.Label(root, text="Senha:").pack()
entry_senha = tk.Entry(root, show="*", width=50); entry_senha.pack()

tk.Label(root, text="GuidTenant:").pack()
entry_tenant = tk.Entry(root, width=50); entry_tenant.pack()

tk.Label(root, text="Ambiente:").pack()
entry_ambiente = tk.Entry(root, width=50); entry_ambiente.pack()

tk.Label(root, text="Empresa:").pack()
entry_empresa = tk.Entry(root, width=50); entry_empresa.pack()

tk.Label(root, text="Nome do Relatório:").pack()
entry_nome = tk.Entry(root, width=50); entry_nome.pack()

tk.Label(root, text="Pasta destino:").pack()
frame_pasta = tk.Frame(root); frame_pasta.pack()
entry_pasta = tk.Entry(frame_pasta, width=40); entry_pasta.pack(side=tk.LEFT)
btn_pasta = tk.Button(frame_pasta, text="Selecionar", command=escolher_pasta)
btn_pasta.pack(side=tk.LEFT)

tk.Label(root, text="Horário de execução (HH:MM):").pack()
entry_hora = tk.Entry(root, width=10); entry_hora.pack()

tk.Label(root, text="Periodicidade:").pack(pady=(10, 0))
combo_periodicidade = ttk.Combobox(root, values=["Diário", "Semanal", "Mensal"], width=15)
combo_periodicidade.pack()

# Botões
frame_botoes = tk.Frame(root); frame_botoes.pack(pady=20)
btn_agendar = tk.Button(frame_botoes, text="Agendar", command=agendar_tarefa, bg="#0078D7", fg="white", width=15)
btn_testar  = tk.Button(frame_botoes, text="Testar Execução", command=testar_execucao, bg="#5cb85c", fg="white", width=18)
btn_apagar  = tk.Button(frame_botoes, text="Apagar", command=apagar_tarefa, bg="#d9534f", fg="white", width=15)
btn_agendar.pack(side=tk.LEFT, padx=5)
btn_testar.pack(side=tk.LEFT, padx=5)
btn_apagar.pack(side=tk.LEFT, padx=5)

# Barra de status
status_label = tk.Label(root, text="Aguardando ação...", bd=1, relief=tk.SUNKEN, anchor="w", fg="gray")
status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

# Lista de widgets que devem ser travados/destravados
inputs_to_toggle = [
    combo_agendamento, entry_usuario, entry_senha, entry_tenant, entry_ambiente,
    entry_empresa, entry_nome, entry_pasta, entry_hora, combo_periodicidade
]
buttons_to_toggle = [btn_carregar, btn_pasta, btn_agendar, btn_testar, btn_apagar]

atualizar_lista_agendamentos()
root.mainloop()
