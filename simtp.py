# ==============================================================================
# SiMTP
#
# Created: 10/7/2018
# Author:  Nelno the Amoeba
#
# Copyright 2018 Jonathan E. Wright
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Description:
# A simple SMTP server used to trigger something when an email is sent.
#
# In particular, this is was written to allow an LaView LV-N9808C8E NVR
# to send motion detection event emails despite its firmware being too old to
# use any public SMTP servers due to SSLV3 support being dropped for security
# reasons around 2016. This server will simply forward emails from the NVR
# to a server specified on the command line.
#
# No other use case is supported or implied.
#
# Only supports dated 'simple' SMTP using HELO not EHLO (SMTP extensions)
# Does not require any authentication from the sender.
#
# WARNING: You should not use this on any public-facing network.
#
# Only connections from the passed IP and the localhost IP (127.0.0.1) will be
# accepted.
#
# Peculiarities:
# - only accepts one connection at a time
# - blocks all over the place and expects a very specific sequence of commands.
#   It is thus probably not useful as a generic SMTP server without significant
#   modification, but it might be useful as an example.
# - Because the LV-N9808C8E NVR firmware appears to have a bug in it that
#   truncates the second of two JPG image email attachments, this server will
#   only forward the first attachment of an incoming email.
# ==============================================================================

#!/usr/bin/python
import socket
import sys
import base64
import smtplib # for sending email
import uuid # for unique file names
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==============================
# printTokens
def printTokens( tokens ):
	i = 0
	for temp in tokens:
		print( i, ": '" + temp + "'" )
		i = i + 1

# ==============================
# tokenize

def tokenize( dataStr, separator ):
	tokens = dataStr.split()
	# printTokens( tokens )
	if ( separator != None ):
		newTokens = []
		for t in tokens:
			tempTokens = t.split( separator )
			if ( len( tempTokens ) == 1 ):
				newTokens.append( t )
			else:
				for tt in tempTokens:
					if ( tt != '' ):
						newTokens.append( tt )
		return newTokens
	return tokens

# ==============================
# waitForResponse
def waitForResponse( conn ):
	data = None
	try:
		data = conn.recv( 4096 )
	except ConnectionAbortedError:
		print( "ConnectionAborted" )

	if data:
		tokens = tokenize( data.decode(), ':' )
		printTokens( tokens )
		return tokens
	else:
		return None

# ==============================
# respond
def respond( conn, code, text ):
	response =  str( code ) + ' ' + text + '\r\n'
	print( 'resp: ' + response )
	conn.send( response.encode() )

# ==============================
# quitConnection

def quitConnection( conn ):
	# these next two lines make thunderbird close the email, which we don't want right now
	# msg = '221 OK\r\n'
	# conn.send( msg.encode() )
	conn.close()
	print( 'Connection closed.' )

# ==============================
# fatalError

def fatalError( tokens, msg ):
	for t in tokens:
		dataStr = dataStr + t
	print( 'ERROR: ' + dataStr )
	print( msg )
	quitConnection( conn )
	sys.exit( 1 )

# ==============================
# error

def error( tokens, expected ):
	for t in tokens:
		dataStr = dataStr + t
	# print( 'ERROR: ' + dataStr )
	# print( msg )
	raise Exception( "ERROR: " + expected + "\r\n" + "RECEIVED: " + dataStr )

# ==============================
# logToFile

def logToFile( mailData ):
	filename = "logs\mail_" + str( uuid.uuid4() ) + ".log"
	with open( filename, "w" ) as textFile:
		print( mailData, file = textFile )

# ==============================
# sendMail

def sendMail( fromaddr, toaddr, outgoingPassword, outgoingServer, outgoingServerPort, mailData ):
	try:
		server = smtplib.SMTP( outgoingServer, outgoingServerPort )
		server.starttls()

		print( "Logging in to " + outgoingServer + " with TLS..." )
		server.login( fromaddr, outgoingPassword )

		# text = msg.as_string()
		print( "Sending mail..." );
		server.sendmail( fromaddr, toaddr, mailData )

		print( "Logging out..." );
		server.quit()

		print( "Mail sent." )
		logToFile( mailData )

	except smtplib.SMTPException as e:
		print( 'ERROR: ' + str( e ) )
	except socket.error as e:
		print( 'SOCKET ERROR: ' + str( e ) )
	except socket.herror as e:
		print( 'SOCKET HERROR: ' + str( e ) )
	except socket.gaierror as e:
		print( 'SOCKET GAI ERROR: ' + str( e ) )
	except socket.timeout as e:
		print( 'SOCKET TIMEOUT ERROR: ' + str( e ) )


# ==============================
# listen

def listen( sock, authIP, fromaddr, toaddr, outgoingPassword, outgoingServer, outgoingServerPort ):
	print( "SiMTP listening..." )
	sock.listen( 1 )

	conn, addr = sock.accept()

	if ( addr[0] != authIP and addr[0] != '127.0.0.1' ):
		print( "Unauthorized access from " + str( addr[0] ) + "!" )
		quitConnection( conn )
		return

	mailData = ''
	truncatedMailData = None

	with conn:
		try:
			clientName = ''
			print( 'Connection from ', addr )
			msg = '220 SiMTP Server Ready\r\n'
			conn.send( msg.encode() )

			tokens = waitForResponse( conn )
			if ( tokens[0] != 'EHLO' and tokens[0] != 'HELO' ):
				error( tokens, 'Unknown response!' )

			# EHLO command
			# don't respond to EHLO, because we don't support SMTP extensions
			if ( tokens[0] == 'EHLO' ):
				# greets is for EHLO only, not EHLO
				# respond( conn, 250, 'SiMTP greets ' + clientName )
				# respond( conn, 250, 'OK' )
				respond( conn, 500, 'Unknown command' )
				# after replying with an error we should get a HELO
				tokens = waitForResponse( conn )

			# HELO command
			if ( tokens[0] != 'HELO' ):
				error( tokens, 'Expected HELO' )
			else:
				# printTokens( tokens )
				respond( conn, 250, "Hello " + clientName )

			if ( len( tokens ) > 1 ):
				clientName = tokens[1]
				print( "Client name: '" + clientName + "'" )

			# MAIL command
			tokens = waitForResponse( conn )
			# printTokens( tokens )

			if ( len( tokens ) < 3 or tokens[0] != 'MAIL' or tokens[1] != 'FROM' ):
				error( tokens, 'Expected MAIL FROM' )

			print( 'MAIL FROM ' + tokens[2] )
			respond( conn, 250, 'OK' )

			# RCPT command
			tokens = waitForResponse( conn )
			# printTokens( tokens )

			if ( len( tokens ) < 3 or tokens[0] != 'RCPT' or tokens[1] != 'TO' ):
				error( tokens, 'Expected RCPT TO' )

			print( 'RCPT TO ' + tokens[2] )
			respond( conn, 250, 'OK' )

			# DATA command
			tokens = waitForResponse( conn )
			printTokens( tokens )

			if ( len( tokens ) != 1 or tokens[0] != 'DATA' ):
				error( tokens, 'Expected DATA' )

			respond( conn, 354, 'Start mail input; end with <CRLF>.<CRLF>' )

			lastLine = ''
			while True:
				data = conn.recv( 4096 )
				if not data:
					print( "No Data!" )
					break
				else:
					dataStr = data.decode()
					mailData += dataStr
					lastTwoLines = lastLine + dataStr
					if ( lastTwoLines.find( '\r\n.\r\n' ) >= 0 ):
						break;
					lastLine = dataStr

			# we truncate the last attachment because it appears the server fails to send
			# all of the data. We can tell because even when we get a <CRLF>.<CRLF> end of
			# input, the base64 mime text is truncated.
			boundaryString = "--#BOUNDARY#";
			lenBoundaryString = len( boundaryString )
			endOfHeader = mailData.find( boundaryString )
			if ( endOfHeader >= 0 ):
				endOfBody = mailData.find( boundaryString, endOfHeader + len( boundaryString ) )
				if ( endOfBody >= 0 ):
					endOfFirstAttachment = mailData.find( boundaryString, endOfBody + lenBoundaryString )
					if ( endOfFirstAttachment >= 0 ):
						truncatedMailData = mailData[:( endOfFirstAttachment + lenBoundaryString )]
					numAttachments = mailData.count( "Content-Disposition: attachment;" )
					print( "Mail: " + mailData[:endOfBody] )
					print( "Mail: +" + str( numAttachments ) + " attachments" )
				else:
					print( "Mail: " + mailData[:endOfHeader] )
			else:
				print( "Mail: " + mailData )

			respond( conn, 250, 'OK' )

			# QUIT
			tokens = waitForResponse( conn )
			if ( tokens != None and len( tokens ) != 1 ):
				error( tokens, 'Expected QUIT' )

			respond( conn, 221, 'SiMTP Service closing transmission channel' )

			quitConnection( conn )
		except Exception as msg:
			print( "ERROR: " + str( msg ) )
			quitConnection( conn )

	if ( truncatedMailData != None ):
		sendMail( fromaddr, toaddr, outgoingPassword, outgoingServer, outgoingServerPort, truncatedMailData )
	else:
		sendMail( fromaddr, toaddr, outgoingPassword, outgoingServer, outgoingServerPort, mailData )

# TODO: figure out how to send a push notification to LaView's Android app

print( "SiMTP v. 1.0\r\n" )
print( "WARNING! You must not use this on any public-facing network!!!" )
print( "Read the license and documentation in simtp.py!\r\n" )

if ( len( sys.argv ) != 8 or not sys.argv[1].isdigit() or not sys.argv[7].isdigit() ):
	print( 'Usage: simtp <port> <authorized_IP> <from_addr> <to_addr> <outgoing_password> <outgoing_server> <outgoing_server_port>' )
	print( 'Connections from other than <authorized_IP> and 127.0.0.1 are refused.' )
	exit()

port = int( sys.argv[1] )
authIP = sys.argv[2]
fromaddr = sys.argv[3]
toaddr = sys.argv[4]
outgoingPassword = sys.argv[5]
outgoingServer = sys.argv[6]
outgoingServerPort = int( sys.argv[7] )

sock = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
sock.bind( ( '', port ) )

while True:
	listen( sock, authIP, fromaddr, toaddr, outgoingPassword, outgoingServer, outgoingServerPort )

print( "This makes no sense" )

sys.exit( 0 )

