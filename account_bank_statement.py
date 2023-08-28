# -*- coding: utf-8 -*-
import json

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'
    _order = 'name ASC'

    balance = fields.Float(compute="compute_balance")
    new_balance = fields.Float(string='new Balance')
    old_balance = fields.Float(string='Old Balance')
    sales_person = fields.Many2one('hr.employee', string="المندوب", )
    period = fields.Selection([('first', "فتره أولي "), ('second', " فتره ثانية "), ('third', "فتره ثالثة "),
                               ('fourth', "فتره رابعة "), ('fifth', "فتره خامسة "), ('six', "فتره سادسة "),
                               ],
                              string="الفترات",
                              required=True)
    move_to_main = fields.Boolean("تحويل للرئيسية", store=True)
    can_edit_balance = fields.Boolean(compute="compute_can_edit_balance")

    # mohamed ****************************************
    hide_cheque_field = fields.Boolean(related='journal_id.allow_cheque', string="Hide Fields")

    # Mohamed ******************************************


    def unlink(self):
        for statement in self:
            deleted_amount = 0
            for rec in self.line_ids:
                deleted_amount += rec.amount
            next_statements = self.env['account.bank.statement'].search([('journal_id', '=', self.journal_id.id)])
            for next_statement in next_statements:
                if next_statement.id > statement.id:
                    next_statement.balance_end_real = next_statement.balance_end_real - deleted_amount
                    next_statement.balance_start = next_statement.balance_start - deleted_amount
                    next_statement._end_balance()
                    break
            # statement.balance_end_real = statement.balance_end_real - rec.amount
        return super(AccountBankStatement, self).unlink()

    @api.onchange('period')
    def compute_can_edit_balance(self):
        for rec in self:
            user = self.env.user
            if user.has_group('treasury.edit_balance_group'):
                rec.can_edit_balance = True
            else:
                rec.can_edit_balance = False

    @api.onchange('balance_end_real')
    def compute_balance(self):
        for rec in self:
            rec.balance = rec.balance_end_real - rec.balance_start

    @api.onchange('balance')
    def onchange_balance(self):
        old = self.new_balance
        self.new_balance = self.balance
        self.old_balance = old

    @api.onchange('old_balance')
    def edit_balance(self):
        for statement in self:
            if statement._origin.id:
                amount = statement.new_balance - statement.old_balance
                if amount > 0.0:
                    next_statements = self.env['account.bank.statement'].search(
                        [('journal_id', '=', self.journal_id.id)])
                    for next_statement in next_statements:
                        if next_statement.id > statement._origin.id:
                            next_statement.balance_end_real = next_statement.balance_end_real + amount
                            next_statement.balance_start = next_statement.balance_start + amount
                            next_statement._end_balance()
                            break
                elif amount < 0.0:
                    test = amount * -1
                    next_statements = self.env['account.bank.statement'].search(
                        [('journal_id', '=', self.journal_id.id)])
                    for next_statement in next_statements:
                        if next_statement.id > statement._origin.id:
                            next_statement.balance_end_real = next_statement.balance_end_real - test
                            next_statement.balance_start = next_statement.balance_start - test
                            next_statement._end_balance()
                            break

    @api.depends('balance_end')
    def _compute_ending_balance(self):
        for statement in self:
            statement.balance_end_real = statement.balance_end

    @api.onchange('line_ids', 'line_ids.date', 'period', 'sales_person')
    def recompute_lines(self):
        for rec in self.line_ids:
            if rec.statement_id.move_to_main:
                rec.payment_ref = 'تحويل للرئيسية'

            else:
                if not rec.sales_person:
                    if not rec.payment_ref:
                        rec.payment_ref = 'سداد ريكويست'
                    rec.sales_person = self.sales_person

            rec.period = self.period
            rec.sales_person = self.sales_person

    def _set_next_sequence(self):
        """Set the next sequence.

        This method ensures that the field is set both in the ORM and in the database.
        This is necessary because we use a database query to get the previous sequence,
        and we need that query to always be executed on the latest data.

        :param field_name: the field that contains the sequence.
        """

        self.ensure_one()
        last_sequence = self._get_last_sequence()
        new = not last_sequence
        if new:
            last_sequence = self._get_last_sequence(relaxed=True) or self._get_starting_sequence()

        format, format_values = self._get_sequence_format_param(last_sequence)
        if new:
            format_values['seq'] = 0
            format_values['year'] = self[self._sequence_date_field].year % (10 ** format_values['year_length'])
            format_values['month'] = self[self._sequence_date_field].month
        format_values['seq'] = format_values['seq'] + 1

        val_string = dict(self._fields['period'].selection).get(self.period)

        if self.period:
            format_values['prefix1'] = val_string

        self[self._sequence_field] = format.format(**format_values)

        self._compute_split_sequence()



    def approve_button_post(self):
        for rec in self:
            if rec.move_to_main:
                if rec.line_ids:
                    rec.line_ids.unlink()
                rec.line_ids = [(0, 0, {
                    'payment_ref': "تحويل للرئيسية",
                    "amount": -rec.balance_start,
                    "date": rec.date,
                    "period": rec.period
                })]
            rec.button_post()

# ******************************************* Mohamed **********************************************************
    def button_validate_or_action(self): # ** Mohamed (this Function) **
        res = super(AccountBankStatement, self).button_validate_or_action()
        bank_statemnts = []
        journals = self.line_ids.mapped('journal_bank')  # all journals
        for journal in journals:
            filtered_journal_lines = self.line_ids.filtered(lambda j: j.journal_bank.id == journal.id)
            for line in filtered_journal_lines:
                if not line.created_bank_statment:
                    self.balance_end_real -= line.amount
                    main = self.env['account.bank.statement'].search([('sales_person','=',line.sales_person.id),
                    ('date','=',line.date),('journal_id','=',line.journal_bank.id),('state','=','open')],limit=1)
                    if main:
                        main.write({
                            'line_ids': [(0, 0, {
                                'payment_ref': ' شيك من عميل ' + str(line.partner_id.name),
                                "amount": line.amount,
                                "date": line.date,
                                "period": line.period,
                                'sales_person': line.sales_person.id,
                                'bank_name': line.bank_name.id,
                                'date_of_cheque': line.date_of_cheque,
                                'cheque_number': line.cheque_number
                            })]
                        })
                    else:
                        data = {
                            'sales_person': line.sales_person.id,
                            'period': line.period,
                            'journal_id':line.journal_bank.id,
                            'line_ids': [(0, 0, {
                                'payment_ref': ' شيك من عميل ' + str(line.partner_id.name),
                                "amount": line.amount,
                                "date": line.date,
                                "period": line.period,
                                'sales_person': line.sales_person.id,
                                'bank_name': line.bank_name.id,
                                'date_of_cheque': line.date_of_cheque,
                                'cheque_number': line.cheque_number
                            })]
                        }
                        bank = self.env['account.bank.statement'].sudo().create(data)
                        line.created_bank_statment = True
                        bank_statemnts.append(bank)
            print(bank_statemnts)
            for post in bank_statemnts:
                post.sudo().button_post()
            print(bank_statemnts)
        result = {
            'res': res,
            'bank_statements': bank_statemnts,
        }
        return result
# ******************************************* Mohamed **********************************************************

    def button_journal_entries(self): # Mohamed (this function)
        return {
            'name': _('Journal Entries'),
            'view_mode': 'tree',
            'res_model': 'account.move.line',
            'view_id': self.env.ref('account.view_move_line_tree_grouped_bank_cash').id,
            'type': 'ir.actions.act_window',
            'domain': [('move_id', 'in', (self.line_ids.move_id.ids + self.line_ids.reversal_move_id.ids))],
            'context': {
                'journal_id': self.journal_id.id,
                'group_by': 'move_id',
                'expand': True
            }
        }
# ******************************************************************************************************************
    def button_reopen(self):
        res = super(AccountBankStatement,self).button_reopen()
        self.line_ids.appear_cancel_button = False
        return res

























































