# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010 Savoir-faire Linux (<http://www.savoirfairelinux.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.tools.translate import _
from openerp import fields, models, api

from openerp.tools import (
    DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT,
)

from datetime import datetime
import time


def _own_company(self):
    """Return the user company id."""
    return self.env.user.company_id.id


class MgmtSystemAudit(models.Model):
    """Model class that manage audit."""
    _name = "mgmtsystem.audit"
    _description = "Audit"
    _inherit = ['mail.thread']
    name = fields.Char('Name', size=50)

    reference = fields.Char(
        'Reference',
        size=64,
        required=True,
        readonly=True,
        default='NEW'
    )
    date = fields.Datetime('Date')
    line_ids = fields.One2many(
        'mgmtsystem.verification.line',
        'audit_id',
        'Verification List',
    )
    number_of_audits = fields.Integer('# of audits', readonly=True, default=1)
    number_of_nonconformities = fields.Integer(
        'Number of nonconformities', readonly=True, store=True,
        compute="_compute_number_of_nonconformities")
    number_of_questions_in_verification_list = fields.Integer(
        'Number of questions in verification list', readonly=True, store=True,
        compute="_compute_number_of_questions_in_verification_list")
    number_of_improvements_opportunity = fields.Integer(
        'Number of improvements Opportunities', readonly=True, store=True,
        compute="_compute_number_of_improvement_opportunities")
    days_since_last_update = fields.Integer(
        'Days since last update', readonly=True, store=True,
        compute="_compute_days_since_last_update")
    closing_date = fields.Datetime('Closing Date', readonly=True)

    number_of_days_to_close = fields.Integer(
        '# of days to close', readonly=True, default=0)

    user_id = fields.Many2one('res.users', 'Audit Manager')
    auditor_user_ids = fields.Many2many(
        'res.users',
        'mgmtsystem_auditor_user_rel',
        'user_id',
        'mgmtsystem_audit_id',
        'Auditors',
    )
    auditee_user_ids = fields.Many2many(
        'res.users',
        'mgmtsystem_auditee_user_rel',
        'user_id',
        'mgmtsystem_audit_id',
        'Auditees',
    )
    strong_points = fields.Text('Strong Points')
    to_improve_points = fields.Text('Points To Improve')
    imp_opp_ids = fields.Many2many(
        'mgmtsystem.action',
        'mgmtsystem_audit_imp_opp_rel',
        'mgmtsystem_action_id',
        'mgmtsystem_audit_id',
        'Improvement Opportunities',
    )

    nonconformity_ids = fields.Many2many(
        'mgmtsystem.nonconformity',
        string='Nonconformities',
    )
    state = fields.Selection(
        [
            ('open', 'Open'),
            ('done', 'Closed'),
        ],
        'State',
        default="open"
    )
    system_id = fields.Many2one('mgmtsystem.system', 'System')
    company_id = fields.Many2one(
        'res.company', 'Company', default=_own_company)

    @api.depends("nonconformity_ids")
    def _compute_number_of_nonconformities(self):
        """Count number of nonconformities."""
        number = 0
        for id in self.nonconformity_ids:
            number = number + 1
        self.number_of_nonconformities = number
        return number

    @api.depends("imp_opp_ids")
    def _compute_number_of_improvement_opportunities(self):
        """Count number of improvements Opportunities."""
        number = 0
        for id in self.imp_opp_ids:
            number = number + 1
        self.number_of_improvements_opportunity = number
        return number

    @api.depends("line_ids")
    def _compute_number_of_questions_in_verification_list(self):
        number = 0
        for id in self.line_ids:
            number = number + 1
        self.number_of_questions_in_verification_list = number
        return number

    @api.depends("write_date")
    def _compute_days_since_last_update(self):
        for audit in self:
            audit.days_since_last_update = audit._elapsed_days(
                audit.create_date,
                audit.write_date)

    @api.model
    def _elapsed_days(self, dt1_text, dt2_text):
        res = 0
        if dt1_text and dt2_text:
            dt1 = fields.Datetime.from_string(dt1_text)
            dt2 = fields.Datetime.from_string(dt2_text)
            res = (dt2 - dt1).days
        return res

    @api.model
    def create(self, vals):
        """Audit creation."""
        vals.update({
            'reference': self.env['ir.sequence'].next_by_code(
                'mgmtsystem.audit'
            ),
        })
        audit_id = super(MgmtSystemAudit, self).create(vals)
        return audit_id

    @api.multi
    def button_close(self):
        """When Audit is closed, post a message to followers' chatter."""
        self.message_post(_("Audit closed"))
        number_of_days_to_close = (
            datetime.now() - datetime.strptime(
                self.create_date, "%Y-%m-%d %H:%M:%S")
        ).days
        return self.write({'state': 'done',
                           'closing_date': time.strftime(DATETIME_FORMAT),
                           'number_of_days_to_close': number_of_days_to_close})

    @api.multi
    def message_auto_subscribe1(self, updated_fields, values=None):
        """Automatically add the Auditors, Auditees and Audit Manager
        to the follow list
        """
        self.ensure_one()
        user_ids = [self.user_id.id]
        user_ids += [a.id for a in self.auditor_user_ids]
        user_ids += [a.id for a in self.auditee_user_ids]

        self.message_subscribe_users(user_ids=user_ids, subtype_ids=None)

        return super(MgmtSystemAudit, self).message_auto_subscribe(
            updated_fields=updated_fields,
            values=values
        )

    def get_action_url(self):
        """
        Return a short link to the audit form view
        eg. http://localhost:8069/?db=prod#id=1&model=mgmtsystem.audit
        """

        base_url = self.env['ir.config_parameter'].get_param(
            'web.base.url',
            default='http://localhost:8069'
        )
        url = ('{}/web#db={}&id={}&model={}').format(
            base_url,
            self.env.cr.dbname,
            self.id,
            self._name
        )
        return url

    def get_lines_by_procedure(self):
        p = []
        for l in self.line_ids:
            if l.procedure_id.id:
                proc_nm = self.pool.get('document.page').read(
                    self.env.cr, self.env.uid, l.procedure_id.id, ['name']
                )
                procedure_name = proc_nm['name']
            else:
                procedure_name = _('Undefined')

            p.append({"id": l.id,
                      "procedure": procedure_name,
                      "name": l.name,
                      "yes_no": "Yes / No"})
        p = sorted(p, key=lambda k: k["procedure"])
        proc_line = False
        q = []
        proc_name = ''
        for i in range(len(p)):
            if proc_name != p[i]['procedure']:
                proc_line = True
            if proc_line:
                q.append({"id": p[i]['id'],
                          "procedure": p[i]['procedure'],
                          "name": "",
                          "yes_no": ""})
                proc_line = False
                proc_name = p[i]['procedure']
            q.append({"id": p[i]['id'],
                      "procedure": "",
                      "name": p[i]['name'],
                      "yes_no": "Yes / No"})
        return q


class MgmtSystemVerificationLine(models.Model):
    """Class to manage verification's Line."""
    _name = "mgmtsystem.verification.line"
    _description = "Verification Line"
    _order = "seq"

    name = fields.Char('Question', required=True)
    audit_id = fields.Many2one(
        'mgmtsystem.audit',
        'Audit',
        ondelete='restrict',
        select=True,
    )
    procedure_id = fields.Many2one(
        'document.page',
        'Procedure',
        ondelete='cascade',
        select=True,
    )
    is_conformed = fields.Boolean('Is conformed', default=False)
    comments = fields.Text('Comments')
    seq = fields.Integer('Sequence')
    company_id = fields.Many2one(
        'res.company', 'Company', default=_own_company)


class MgmtSystemNonconformity(models.Model):
    """Class use to add audit_ids association to MgmtSystemNonconformity."""
    _name = "mgmtsystem.nonconformity"
    _inherit = "mgmtsystem.nonconformity"
    audit_ids = fields.Many2many(
        'mgmtsystem.audit', string='Related Audits')
