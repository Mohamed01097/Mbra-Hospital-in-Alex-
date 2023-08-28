# -*- coding: utf-8 -*-
import json

from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'
    _order = 'id'

    sales_person = fields.Many2one('hr.employee',string= "المندوب", )
    period = fields.Selection([('first', "فتره أولي "), ('second', " فتره ثانيه "), ('third', "فتره ثالثه "),
                               ('fourth', "فتره رابعة "), ('fifth', "فتره خامسة "), ('six', "فتره سادسة ")],
                              string="الفترات")
    employee_ids = fields.Many2many('hr.employee', compute="_compute_employee_ids", store=True)

# ******************************************* Mohamed **********************************************************
    bank_name = fields.Many2one('bank.name',string='Bank Name') # Mohamed                                      *
    date_of_cheque = fields.Date(required=False, string='Cheque Date') # Mohamed                               *
    cheque_number = fields.Char(required=False, string='Cheque Number') # Mohamed                           *
    journal_bank = fields.Many2one('account.journal', string="Journal Bank", required=False) # Mohamed         *
                                   # domain=[('allow_cheque', '=', True)])
    allow_cheque = fields.Boolean(related='journal_id.allow_cheque', readonly=True, store=True) # Mohamed      *
    journal_required_if_reconcile = fields.Boolean(default=False,store=True,readonly=True) # Mohamed           *
    created_bank_statment = fields.Boolean() # Mohamed                                                         *
    is_canceled = fields.Boolean() # Mohamed                                                                   *
    appear_cancel_button = fields.Boolean(default=False)
    journal_name = fields.Char(related='journal_id.name',readonly=True)


# ******************************************* Mohamed **********************************************************

    @api.depends('partner_id')
    def _compute_employee_ids(self):
        result_list = []
        for sales_person in self.partner_id.sales_persons:
            result_list.append(sales_person.id)
        employee_ids = self.env['hr.employee'].search([('is_sales_person', '=', True), ('id', 'in', result_list)])
        for rec in self:
            rec.employee_ids = [(6, 0, employee_ids.ids)]

    @api.model
    def create(self, vals_list):
        print(vals_list)
        if vals_list.get("amount",0) < 0:
            bnk_stmt_obj = self.env['account.bank.statement'].browse(vals_list.get("statement_id"))
            if  not bnk_stmt_obj.journal_id.allow_negative and not bnk_stmt_obj.move_to_main:
                raise UserError("The amount cannot be less than zero")

        res = super(AccountBankStatementLine, self).create(vals_list)
        res.move_id.sales_person = res.sales_person.id
        res.move_id.period = res.period
        return res

    def write(self, vals):
        if vals.get("amount",0) < 0 :
            if not self.statement_id.journal_id.allow_negative  and not self.statement_id.move_to_main:
                raise UserError("The amount cannot be less than zero")

        res = super(AccountBankStatementLine, self).write(vals)
        return res

# ******************************************* Mohamed **********************************************************

    def cancel_cheque(self):
        self.appear_cancel_button = False
        self.is_canceled = True
        reversed_moves = self.move_id._reverse_moves(cancel=True)
        self.reversal_move_id = reversed_moves.ids
        print(self.reversal_move_id)

# ******************************************* Mohamed **********************************************************

    def button_undo_reconciliation(self):
        self.appear_cancel_button = True
        return super(AccountBankStatementLine,self).button_undo_reconciliation()





class BankName(models.Model):
    _name = 'bank.name'

    name = fields.Char()
