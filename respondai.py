#!/usr/bin/python
# -*- coding: latin-1 -*-
import web, shutil, sys, smtplib, calendar, psycopg2, base64, time, datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from datetime import timedelta


render = web.template.render('templates/', base='layout', globals={ 'str': str, 'date': date })
db = web.database(dbn='postgres', user='postgres', pw='postgres!23', db='respondai')
ip = "respondai-waltercmg.c9users.io"
#ip = "10.32.64.91:8080"
#http://webpy.org/cookbook/storeupload/
conexao = psycopg2.connect(database='respondai', user='postgres', password='postgres!23') 
cursor = conexao.cursor()

# para instalar o psycopg2: sudo pip install django psycopg2
# para configurar o postgres:
#    sudo vi /etc/postgresql/9.3/main/pg_hba.conf
#    trocar a linha local   all             postgres                                peer POR
#                   local   all             postgres                                md5
#    restartar o postgres: sudo service postgresql restart

urls = (
    '/', 'index',
    '/ad', 'add_antigo',
    '/add', 'add',
    '/resposta', 'resposta',
    '/responder', 'responder',
    '/listar', 'listar',
    '/resumo', 'resumo',
    '/consolidar', 'consolidar',
    '/painel', 'painel',
    '/login', 'login'
)

class index:
    def GET(self):  
       todos = db.select('usuario', order="nome, tipo")
       return render.inserir(todos ,ip)

class login:
    def GET(self):  
       todos = db.select('usuario', where="tipo=1", order="nome, tipo")
       return render.login(todos)

class painel:
    def GET(self):
       usuario = None
       i = web.input(id_usuario=None)
       if i.id_usuario:
          myvar = dict(id_usuario=int(i.id_usuario))
          usuario = db.select('usuario', myvar, where="id_usuario = $id_usuario")
       return render.painel(usuario, ip)

class listar:
    def GET(self):
        i = web.input(id_usuario="", pendentes="", mes=str(date.today().month), ano=str(date.today().year))
        nm_usu = ""
        comp_titulo = ""
        n_mes = int(i.mes)
        n_ano = int(i.ano)
        if i.id_usuario!="":
            cursor.execute("SELECT nome FROM usuario WHERE id_usuario=%s", (i.id_usuario, ))
            u = cursor.fetchone()
            nm_usu = u[0]
            
            if i.pendentes!="":
                filtro = 'AND resposta IS NULL'
                comp_titulo = "(PENDENTES)"
            else:
                filtro = ''
                comp_titulo = "(COMPLETO)"
            todos = db.query('SELECT coleta.id_coleta, titulo, prazo, resposta, nome FROM coleta, coleta_usuario, usuario '+
                             'WHERE coleta.id_coleta=coleta_usuario.id_coleta AND coleta_usuario.id_usuario = usuario.id_usuario '+
                             'AND coleta_usuario.id_usuario=$i.id_usuario '+filtro+' AND date_part(\'year\', prazo) = $i.ano and ' +
                             'date_part(\'month\', prazo) = $i.mes ' +
                             'ORDER BY prazo', vars=locals())
        else:
            nm_usu = "ECAD"
            todos = db.select('coleta',  where="date_part('year', prazo) = $i.ano and " + 
                              "date_part('month', prazo) = $i.mes", vars=locals(), order="prazo")       
        c = calendar.HTMLCalendar(calendar.SUNDAY).formatmonth(n_ano, n_mes)
        c=c.replace("<td", "<td align=center valign=top width=150 height=70")
        c=c.replace("<table", "<table align=center class='estiloTabelaGenerica' border=1")

        for todo in todos:   
            dia = str(int(todo.prazo.strftime('%d')))
            if i.id_usuario:
                if todo.resposta:
                    cor = "#99ff99"
                else:
                    cor = "#ff9999"
                c=c.replace(">" + dia + "<", " bgcolor='"+cor+"'>" + dia + "<br><a href='http://"+ip+
                            "/resposta?id_coleta="+str(todo.id_coleta)+"&id_usuario="+
                            i.id_usuario+"'>"+todo.titulo+"</a><")  
            else:
                c=c.replace(">" + dia + "<", " bgcolor=#ccffff>" + dia + "<br><a href='http://"+ip+
                            "/resumo?id_coleta="+str(todo.id_coleta)+"'>"+todo.titulo+"</a><")  
        naveg = "http://"+ip+"/listar?id_usuario="+i.id_usuario+"&pendentes="+i.pendentes
        data = datetime.datetime(n_ano,n_mes,1)
        ante = data + datetime.timedelta(days=-5)
        prox = data + datetime.timedelta(days=31)
        url_ante = naveg + "&mes="+str(ante.month)+"&ano="+str(ante.year)
        url_prox = naveg + "&mes="+str(prox.month)+"&ano="+str(prox.year)
        titulo = "CALENDÁRIO <b>"+str(nm_usu)+"</b> " + str(comp_titulo)
        return render.listar(titulo, c, url_ante, url_prox, i.id_usuario, ip)

class resumo:
    def GET(self):         
       i = web.input(id_coleta=None)
       todos = db.query('SELECT * FROM coleta, coleta_usuario, usuario WHERE coleta.id_coleta=coleta_usuario.id_coleta AND '+           
                        'coleta_usuario.id_usuario=usuario.id_usuario AND coleta.id_coleta=$id_coleta '+
                        'ORDER BY nome', vars={'id_coleta': int(i.id_coleta)})
       return render.resumo(todos)
                 
class consolidar:

    def POST(self):         
       i = web.input()              
       titulo, corpo = self.get_texto_consol(i.id_coleta) 
       print "AQUIIIIII: "+corpo
       self.enviar_email(i.para, titulo, corpo)
       todos = db.select('coleta', order="prazo")       
       c = calendar.HTMLCalendar(calendar.SUNDAY)
       return render.painel(None, ip)

    def get_texto_consol(self, id_coleta):
       titulo = ""
       texto = ""
       todos = db.query('SELECT * FROM coleta, coleta_usuario, usuario WHERE coleta.id_coleta=coleta_usuario.id_coleta AND '+           
                        'coleta_usuario.id_usuario=usuario.id_usuario AND coleta.id_coleta=$id_coleta '+
                        'ORDER BY nome', vars={'id_coleta': int(id_coleta)})
       for todo in todos:
           titulo = todo.titulo
           if todo.resposta == None:
              todo.resposta = "Sem resposta."
           texto = texto + "<b>" + todo.nome + "</b>: <br><br>" + str(todo.resposta) + "<br><br>"
       titulo = "[respondai] Respostas de: " + titulo
       texto = "Seguem respostas:<br><br>" + texto
       return titulo, texto

    def enviar_email(self, destinatario, titulo, corpo):
        me = "respondai@serpro.gov.br"
        you = destinatario

        msg = MIMEMultipart('alternative')
        msg['Subject'] = titulo
        msg['From'] = me
        msg['To'] = you

        text = "Teste"
        html = corpo

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')

        msg.attach(part1)
        msg.attach(part2)
        s = smtplib.SMTP('localhost')
        s.sendmail(me, you, msg.as_string())

class add:
   
    def send_mail(self, destinatario, titulo, id_coleta, prazo, id_usuario, usuario):
        me = "respondai@serpro.gov.br"
        you = destinatario
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "[respondai] - " + titulo
        msg['From'] = me
        msg['To'] = you

        text = "Hi!\nHow are you?\nHere is the link you wanted:\nhttps://www.python.org"
        html = "<html><head></head><body><p><br>Prezado,<br><br>"+\
        	   "Favor responder a esta <a href=\"http://"+ip+"/resposta?id_coleta=" + str(id_coleta) +\
               "&id_usuario="+str(id_usuario)+"\">"+\
               "solicitação</a>"+\
               "&nbsp;antes de " + str(prazo) + "</p></body></html>"

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')

        msg.attach(part1)
        msg.attach(part2)

        s = smtplib.SMTP('localhost')
        s.sendmail(me, you, msg.as_string())

    def POST(self):
        i = web.input(destinatario = [], anexo1={})
        if 'anexo1' in i:
            #n = db.insert('coleta', titulo=i.titulo, conteudo=i.conteudo, 
            #exige_resposta=i.exige, prazo=i.prazo, seqname='coleta_id_coleta_seq')    
            # TRATAMENTO DE ANEXO #
            n = db.insert('coleta', titulo=i.titulo, conteudo=i.conteudo, 
            exige_resposta=i.exige, prazo=i.prazo, nm_anexo1=i.anexo1.filename, 
            anexo1=base64.b64encode(i.anexo1.file.read()), seqname='coleta_id_coleta_seq')
        else:
            n = db.insert('coleta', titulo=i.titulo, conteudo=i.conteudo, 
            exige_resposta=i.exige, prazo=i.prazo, seqname='coleta_id_coleta_seq')    
        for d in i.destinatario:                      
           cursor.execute("SELECT id_usuario, nome FROM usuario WHERE nome IN " +
                          "(SELECT nome FROM usuario WHERE id_usuario=%s) " +
                          "AND tipo = 1", (d, ))
           usu_princ = cursor.fetchone()
           cursor.execute("SELECT email, tipo FROM usuario WHERE id_usuario=%s", (d, ))
           usu_email = cursor.fetchone()
           coletas = db.select('coleta_usuario', where="id_usuario = $usu_princ[0] and id_coleta=$n", vars=locals())
           if len(coletas) == 0:
	           v = db.insert('coleta_usuario', id_coleta=n, id_usuario=usu_princ[0])          
           #self.send_mail(str(usu_email[0]), i.titulo, n, i.prazo, usu_princ[0], usu_princ[1])            
        return render.painel(None, ip) 



class add_antigo:
   
    def send_mail(self, destinatario, titulo, id_coleta, prazo, id_usuario, usuario):
        me = "respondai@serpro.gov.br"
        you = destinatario
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "[respondai] - " + titulo
        msg['From'] = me
        msg['To'] = you

        text = "Hi!\nHow are you?\nHere is the link you wanted:\nhttps://www.python.org"
        html = "<html><head></head><body><p><br>Prezado,<br><br>"+\
        	   "Favor responder a esta <a href=\"http://"+ip+"/resposta?id_coleta=" + str(id_coleta) +\
               "&id_usuario="+str(id_usuario)+"\">"+\
               "solicitação</a>"+\
               "&nbsp;antes de " + str(prazo) + "</p></body></html>"

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')

        msg.attach(part1)
        msg.attach(part2)

        s = smtplib.SMTP('localhost')
        s.sendmail(me, you, msg.as_string())

    def POST(self):
        i = web.input(destinatario = [], anexo1={})
        if 'anexo1' in i:
            n = db.insert('coleta', titulo=i.titulo, conteudo=i.conteudo, 
            exige_resposta=i.exige, prazo=i.prazo, seqname='coleta_id_coleta_seq')    
            # TRATAMENTO DE ANEXO #
            #n = db.insert('coleta', titulo=i.titulo, conteudo=i.conteudo, 
            #exige_resposta=i.exige, prazo=i.prazo, nm_anexo1=i.anexo1.filename, 
            #anexo1=base64.b64encode(i.anexo1.file.read()), seqname='coleta_id_coleta_seq')
        else:
            n = db.insert('coleta', titulo=i.titulo, conteudo=i.conteudo, 
            exige_resposta=i.exige, prazo=i.prazo, seqname='coleta_id_coleta_seq')    
        for d in i.destinatario:                      
           cursor.execute("SELECT id_usuario, nome FROM usuario WHERE nome IN " +
                          "(SELECT nome FROM usuario WHERE id_usuario=%s) " +
                          "AND tipo = 1", (d, ))
           usu_princ = cursor.fetchone()
           cursor.execute("SELECT email, tipo FROM usuario WHERE id_usuario=%s", (d, ))
           usu_email = cursor.fetchone()
           coletas = db.select('coleta_usuario', where="id_usuario = $usu_princ[0] and id_coleta=$n", vars=locals())
           if len(coletas) == 0:
	           v = db.insert('coleta_usuario', id_coleta=n, id_usuario=usu_princ[0])          
           self.send_mail(str(usu_email[0]), i.titulo, n, i.prazo, usu_princ[0], usu_princ[1])            
        return render.painel(None, ip) 


class responder:
    def POST(self):
        i = web.input(anexo1={})
        if 'anexo1' in i:           
            n = db.update('coleta_usuario', where='id_coleta = $i.id_coleta and id_usuario=$i.remetente', resposta=i.conteudo, vars=locals())
            # TRATAMENTO DE ANEXO #
            #n = db.update('coleta_usuario', where='id_coleta = $i.id_coleta and id_usuario=$i.remetente', 
            #resposta=i.conteudo, anexo1=base64.b64encode(i.anexo1.file.read()), vars=locals())
        else:
            n = db.update('coleta_usuario', where='id_coleta = $i.id_coleta and id_usuario=$i.remetente', resposta=i.conteudo, vars=locals())
        usuario = db.select('usuario', where="id_usuario = $i.remetente", vars=locals())
        return render.painel(usuario, ip)        


class resposta:
    def GET(self):         
        i = web.input(id_coleta=None, ip=ip)
        myvar = dict(id_coleta=i.id_coleta)
        coleta = db.select('coleta', myvar, where="id_coleta = $id_coleta")
       
        # TRATAMENTO DE ANEXO #
        cursor.execute("SELECT anexo1, nm_anexo1 FROM coleta WHERE id_coleta=%s", (i.id_coleta, ))
        arq = cursor.fetchone()
        if len(str(arq[1])) > 0:
            nm_arq_orig = str(arq[1])
            nm_arq_gerado = nm_arq_orig[:-4] + str(time.time()) + nm_arq_orig[-4:]
            path_arq = "static/anexos/"+nm_arq_gerado
            open(path_arq, 'w+r').write(base64.b64decode(arq[0]))
            link_anexo = "<a href='" + path_arq + "'>" + nm_arq_orig + "</a>"        
        else:
            link_anexo = "(sem anexo)"
        cursor.execute("SELECT  nome FROM usuario WHERE id_usuario=%s", (i.id_usuario, ))
        usuario = cursor.fetchone()
        cursor.execute("SELECT  resposta FROM coleta_usuario WHERE id_usuario=%s AND id_coleta=%s", (i.id_usuario, i.id_coleta))
        resp = cursor.fetchone()
        if resp[0]:
            resposta = str(resp[0])
        else:
            resposta = ""        
        return render.resposta(coleta, i.id_usuario, str(usuario[0]), resposta, ip, link_anexo)


class resposta_anexo:
    def GET(self):         
        i = web.input(id_coleta=None, ip=ip)
        myvar = dict(id_coleta=i.id_coleta)
        coleta = db.select('coleta', myvar, where="id_coleta = $id_coleta")
       
        # TRATAMENTO DE ANEXO #
        #cursor.execute("SELECT anexo1, nm_anexo1 FROM coleta WHERE id_coleta=%s", (i.id_coleta, ))
        #arq = cursor.fetchone()
        #if len(str(arq[1])) > 0:
        #    nm_arq_orig = str(arq[1])
        #    nm_arq_gerado = nm_arq_orig[:-4] + str(time.time()) + nm_arq_orig[-4:]
        #    path_arq = "anexos/"+nm_arq_gerado
        #    open(path_arq, 'w+r').write(base64.b64decode(arq[0]))
        #    link_anexo = "<a href='" + path_arq + "'>" + nm_arq_orig + "</a>"        
        cursor.execute("SELECT  nome FROM usuario WHERE id_usuario=%s", (i.id_usuario, ))
        usuario = cursor.fetchone()
        cursor.execute("SELECT  resposta FROM coleta_usuario WHERE id_usuario=%s AND id_coleta=%s", (i.id_usuario, i.id_coleta))
        resp = cursor.fetchone()
        if resp[0]:
            resposta = str(resp[0])
        else:
            resposta = ""        
        return render.resposta(coleta, i.id_usuario, str(usuario[0]), resposta, ip)


if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()