from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time


def transferir_chamada():
    # --- CONFIGURAÇÃO INICIAL ---
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    print("Conectando ao navegador aberto...")
    try:
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, 10)
    except Exception:
        print("Erro: Não foi possível conectar ao Chrome na porta 9222.")
        return

    print("\n--- INICIANDO INTEGRAÇÃO DE CHAMADA ---")

    # --- IDENTIFICAÇÃO DAS ABAS ---
    aba_estado = None
    aba_meu_site = None

    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        url_atual = driver.current_url.lower()

        if "profkazenski.com" in url_atual:
            aba_meu_site = handle
        elif "cadfaltaschamadaemsala" in url_atual or "sed.sc.gov.br" in url_atual:
            aba_estado = handle

    if not aba_estado or not aba_meu_site:
        print("ERRO: Certifique-se de que a aba de Chamada do seu site e a do Estado estão abertas!")
        return

    # ==========================================
    # 1. LER CHAMADA DO SEU SITE (profkazenski.com)
    # ==========================================
    driver.switch_to.window(aba_meu_site)
    print("\n[1/2] Lendo status de presença em profkazenski.com...")
    time.sleep(2)

    dicionario_chamada = {}

    try:
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "button.selected")))
        botoes_selecionados = driver.find_elements(
            By.CSS_SELECTOR, "button.selected")

        for botao in botoes_selecionados:
            try:
                classes_botao = botao.get_attribute("class").lower()
                status = "P"  # Padrão Presente

                if "ausente" in classes_botao:
                    status = "F"
                elif "justificado" in classes_botao:
                    status = "J"

                # CORREÇÃO: A página de chamadas usa DIVs com a classe 'student-row', e não TRs
                linha_aluno = botao.find_element(
                    By.XPATH, "./ancestor::div[contains(@class, 'student-row')]")

                # Pega todo o texto da linha (nome + botões) e quebra nos "Enters" (\n)
                texto_linha = linha_aluno.text.strip()

                if texto_linha:
                    # A primeira informação em texto dentro dessa div sempre é o nome do aluno
                    nome_aluno = texto_linha.split('\n')[0].strip().upper()

                    # Adiciona ao dicionário apenas se for um nome válido
                    if nome_aluno and nome_aluno != "TODOS P":
                        dicionario_chamada[nome_aluno] = status
                        print(f"    [+] Lido: {nome_aluno} | Status: {status}")

            except Exception as e:
                # Ocultando o erro no terminal para não poluir, mas ele pula para o próximo botão
                continue

        print(
            f"\n-> Sucesso! Chamada de {len(dicionario_chamada)} alunos guardada na memória.")

    except Exception as e:
        print(f"Erro ao ler a chamada: {str(e)}")
        return

    if len(dicionario_chamada) == 0:
        print("Nenhum aluno encontrado. Operação cancelada.")
        return

    # ==========================================
    # 2. PREENCHER O PORTAL DO ESTADO
    # ==========================================
    driver.switch_to.window(aba_estado)
    print("\n[2/2] Lançando faltas no portal do Estado...")
    time.sleep(1.5)

    try:
        # CAPTURA O TOTAL DE AULAS
        try:
            campo_total_aulas = driver.find_element(By.ID, "vNUMTOTALAULAS")
            total_aulas = int(campo_total_aulas.get_attribute("value"))
            print(f" -> Total de aulas detectado: {total_aulas}")
        except:
            total_aulas = 1
            print(" -> [!] Total de aulas não detectado. Usando 1.")

        # CORREÇÃO CRÍTICA: 'Gridfaltas' com 'f' minúsculo, exatamente como no HTML do Estado
        linhas_estado = driver.find_elements(
            By.XPATH, "//tr[contains(@id, 'GridfaltasContainerRow_')]")
        alunos_atualizados = 0

        if len(linhas_estado) == 0:
            print(
                " [!] ATENÇÃO: Nenhuma linha de aluno encontrada. A tabela pode estar oculta ou carregando.")

        for i in range(len(linhas_estado)):
            try:
                # Recarrega a tabela a cada aluno
                tabela_atualizada = driver.find_elements(
                    By.XPATH, "//tr[contains(@id, 'GridfaltasContainerRow_')]")
                if i >= len(tabela_atualizada):
                    break
                linha_atual = tabela_atualizada[i]

                # Extrai o texto da linha ignorando a formatação HTML
                texto_linha = linha_atual.get_attribute("textContent").upper()

                nome_encontrado = None
                for nome_dict in dicionario_chamada.keys():
                    if nome_dict in texto_linha:
                        nome_encontrado = nome_dict
                        break

                if nome_encontrado:
                    status_kazenski = dicionario_chamada[nome_encontrado]

                    try:
                        # Busca o link da presença pelo href (também com 'f' minúsculo)
                        botao_presenca = linha_atual.find_element(
                            By.XPATH, ".//a[contains(@href, 'Gridfaltas')]")
                        # textContent puxa o texto, mesmo que esteja aninhado dentro de um <text>1F</text>
                        status_estado = botao_presenca.get_attribute(
                            "textContent").strip().upper()
                    except Exception:
                        status_estado = "ERRO_LEITURA"

                    # Regra: Só clica se for F ou J no seu site, e C no Estado
                    if status_kazenski in ["F", "J"] and status_estado == "C":
                        if status_kazenski == "F":
                            qtd_cliques = total_aulas
                            texto_acao = f"{total_aulas}F (Falta)"
                        else:
                            qtd_cliques = 9 + total_aulas
                            texto_acao = f"{total_aulas}J (Justificado)"

                        print(
                            f" -> Lançando {texto_acao} para {nome_encontrado} ({qtd_cliques} cliques)...")

                        # Inicia os múltiplos cliques
                        for clique in range(qtd_cliques):
                            try:
                                # Recarrega o elemento exato antes de cada clique (devido ao AJAX do Genexus)
                                tab_loop = driver.find_elements(
                                    By.XPATH, "//tr[contains(@id, 'GridfaltasContainerRow_')]")
                                botao_loop = tab_loop[i].find_element(
                                    By.XPATH, ".//a[contains(@href, 'Gridfaltas')]")

                                driver.execute_script(
                                    "arguments[0].scrollIntoView({block: 'center'});", botao_loop)
                                time.sleep(0.1)
                                botao_loop.click()
                                # Intervalo vital para a página processar a mudança da tag <text>
                                time.sleep(0.4)

                            except Exception as e_clique:
                                print(
                                    f"      [X] Falha no clique {clique+1}: {e_clique}")
                                break

                        alunos_atualizados += 1

                    # LOG de feedback caso o estado já esteja preenchido ou diferente de C
                    elif status_kazenski in ["F", "J"] and status_estado != "C":
                        print(
                            f"    [-] Pulou {nome_encontrado}: Seu site = '{status_kazenski}', Estado já está como '{status_estado}'")

            except Exception as e_linha:
                print(f"    [!] Erro na linha {i}: {e_linha}")
                continue

        print(
            f"\n*** MAGNÍFICO! Integração concluída. {alunos_atualizados} alunos atualizados. ***")

    except Exception as e:
        print(f"Erro geral no portal do Estado: {str(e)}")


if __name__ == "__main__":
    transferir_chamada()
