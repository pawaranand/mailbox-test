# -*- coding: utf-8 -*-
# Copyright (c) 2015, New Indictrans Technologies Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_add, cint, get_datetime, DATE_FORMAT
from frappe.email.smtp import SMTPServer
from frappe.email.receive import POP3Server, Email
from poplib import error_proto
from frappe import _
import datetime

class EmailConfig(Document):

	def autoname(self):
		"""Set name as `email_account_name` or make title from email id."""
		if not self.email_account_name:
			self.email_account_name = self.email_id.split("@", 1)[0]\
				.replace("_", " ").replace(".", " ").replace("-", " ").title()

			self.email_account_name = self.email_account_name 

		self.name = self.email_account_name

	def validate(self):
		"""
			Validations:
				1.validate proper email
				2.Same email id should not be entered by same user
				3.Currently check that only users having trufil domain allowed(Remaining)
				4.Check SMTP and POP
		"""
		if self.email_id:
			validate_email_add(self.email_id, True)
			self.validate_duplicate_emailid_config()

		if self.enabled:
			self.get_pop3()
			self.check_smtp()

	def validate_duplicate_emailid_config(self):
		#check email config exists for same user if yes throw exception
		email_config = frappe.db.get_value("Email Config",
			{"user":self.user,"email_id":self.email_id},"name")

		if email_config and not email_config == self.name and cint(self.get("__islocal")):
			frappe.throw(_("Configuration for {0} Already Exists.").format(self.email_id))


	def check_smtp(self):
		#check SMTP server valid or not
		if not self.smtp_server:
			frappe.throw(_("{0} is required").format("SMTP Server"))

		server = SMTPServer(login = self.email_id,
			password = self.password,
			server = self.smtp_server,
			port = cint(self.smtp_port),
			use_ssl = cint(self.use_tls)
		)
		server.sess

	def get_pop3(self):
		"""Returns logged in POP3 connection object."""
		
		args = {
			"host": self.pop3_server,
			"use_ssl": self.use_ssl,
			"username": self.email_id,
			"password": self.password
		}

		if not self.pop3_server:
			frappe.throw(_("{0} is required").format("POP3 Server"))

		pop3 = POP3Server(frappe._dict(args))
		try:
			pop3.connect()
		except error_proto, e:
			frappe.throw(e.message)

		return pop3

	def receive(self):
		"""Called by scheduler to receive emails from this EMail account using POP3."""
		if self.enabled:
			pop3 = self.get_pop3()
			incoming_mails = pop3.get_messages()

			exceptions = []
		
			for raw in incoming_mails:
				try:
					self.insert_communication(raw)

				except Exception:
					frappe.db.rollback()
					exceptions.append(frappe.get_traceback())

				else:
					frappe.db.commit()

			if exceptions:
				raise Exception, frappe.as_json(exceptions)

	def insert_communication(self, raw):
		email = Email(raw)
		date = datetime.datetime.strptime(email.date,'%Y-%m-%d %H:%M:%S').strftime('%d-%m-%Y %H:%M:%S')
		communication = frappe.get_doc({
			"doctype": "Inbox",
			"subject": email.subject,
			"content": email.content,
			"sender_full_name": email.from_real_name,
			"from": email.from_email,
			"email_account": self.name,
			"user":self.user,
			"date_time":date
		})

		#self.set_thread(communication, email)

		communication.insert(ignore_permissions = 1)
		#communication.submit()

		# save attachments
		email.save_attachments_in_doc(communication)

		# if self.enable_auto_reply and getattr(communication, "is_first", False):
		# 	self.send_auto_reply(communication, email)

		# notify all participants of this thread
		# convert content to HTML - by default text parts of replies are used.
		# communication.content = markdown2.markdown(communication.content)
		# communication.notify(attachments=email.attachments, except_recipient = True)

	def on_update(self):
		self.receive()

