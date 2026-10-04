# Abrir o EcoPulse

1. Extraia EcoPulse-fonte.zip. A pasta EcoPulse contém o código, README e scripts.
2. Com Python 3.11+ instalado, abra PowerShell nessa pasta e execute:

~~~powershell
.\scripts\run_demo.ps1
~~~

3. Mantenha esse terminal aberto. Em outro terminal, crie os exemplos da apresentação:

~~~powershell
.\backend\.venv\Scripts\python.exe scripts/seed_demo.py
~~~

4. Instale EcoPulse-demo.apk no Android. Em **Conexão e informações**, informe http://IP_DO_COMPUTADOR:8000. Celular e computador precisam estar na mesma rede. No emulador Android, o endereço é http://10.0.2.2:8000.
5. Para abrir a prévia no Chrome, com Flutter instalado:

~~~powershell
.\scripts\run_mobile.ps1 -Device chrome
~~~

O APK usa assinatura de desenvolvimento e não é uma publicação na loja. Os exemplos são fictícios e estão identificados no app.

Leia docs/APRESENTACAO.md para o roteiro e docs/VALIDACAO.md para os testes e pendências. O modo demo é local; a arquitetura distribuída usa os arquivos de infra/ e exige Docker. iOS depende de compilação em Mac/Xcode.
