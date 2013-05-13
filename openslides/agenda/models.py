#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    openslides.agenda.models
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Models for the agenda app.

    :copyright: 2011, 2012 by OpenSlides team, see AUTHORS.
    :license: GNU GPL, see LICENSE for more details.
"""

import string

from datetime import datetime

from django.db import models
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy, ugettext_noop, ugettext as _

from mptt.models import MPTTModel, TreeForeignKey

from openslides.utils.exceptions import OpenSlidesError
from openslides.config.api import config
from openslides.projector.projector import SlideMixin
from openslides.projector.api import get_slide_from_sid
from openslides.utils.person.models import PersonField

import roman

import logging
logger = logging.getLogger(__name__)

class Item(MPTTModel, SlideMixin):
    """
    An Agenda Item

    MPTT-model. See http://django-mptt.github.com/django-mptt/
    """
    prefix = 'item'

    AGENDA_ITEM = 1
    ORGANIZATIONAL_ITEM = 2

    ITEM_TYPE = (
        (AGENDA_ITEM, ugettext_lazy('Agenda item')),
        (ORGANIZATIONAL_ITEM, ugettext_lazy('Organizational item')))

    title = models.CharField(null=True, max_length=255, verbose_name=ugettext_lazy("Title"))
    """
    Title of the agenda item.
    """

    text = models.TextField(null=True, blank=True, verbose_name=ugettext_lazy("Text"))
    """
    The optional text of the agenda item.
    """

    comment = models.TextField(null=True, blank=True, verbose_name=ugettext_lazy("Comment"))
    """
    Optional comment to the agenda item. Will not be shown to normal users.
    """

    additional_item = models.BooleanField(default=False, verbose_name=ugettext_lazy("Additional item"))
    """
    Indicates whether this item has been added after agenda is already fixed.
    """

    closed = models.BooleanField(default=False, verbose_name=ugettext_lazy("Closed"))
    """
    Flag, if the item is finished.
    """

    weight = models.IntegerField(default=0, verbose_name=ugettext_lazy("Weight"))
    """
    Weight to sort the item in the agenda.
    """

    parent = TreeForeignKey('self', null=True, blank=True,
                            related_name='children')
    """
    The parent item in the agenda tree.
    """

    type = models.IntegerField(max_length=1, choices=ITEM_TYPE,
                               default=AGENDA_ITEM, verbose_name=ugettext_lazy("Type"))
    """
    Type of the agenda item.

    See Agenda.ITEM_TYPE for more informations.
    """

    duration = models.CharField(null=True, blank=True, max_length=5,
                                verbose_name=ugettext_lazy("Duration (hh:mm)"))
    """
    The intended duration for the topic.
    """

    related_sid = models.CharField(null=True, blank=True, max_length=63)
    """
    Slide-ID to another object to show it in the agenda.

    For example a motion or assignment.
    """

    speaker_list_closed = models.BooleanField(
        default=False, verbose_name=ugettext_lazy("List of speakers is closed"))
    """
    True, if the list of speakers is closed.
    """

    def get_related_slide(self):
        """
        return the object, of which the item points.
        """
        object = get_slide_from_sid(self.related_sid, element=True)
        if object is None:
            self.title = 'Item for deleted slide: %s' % self.related_sid
            self.related_sid = None
            self.save()
            return self
        else:
            return object

    def get_related_type(self):
        """
        return the type of the releated slide.
        """
        return self.get_related_slide().prefix

    def print_related_type(self):
        """
        Print the type of the related item.

        For use in Template
        ??Why does {% trans item.print_related_type|capfirst %} not work??
        """
        return _(self.get_related_type().capitalize())


    def get_item_no(self):
        """
        :return: the number of this agenda item
        """
        if self.additional_item:
            prev_sibling = self._get_prev_sibling(lambda add_item: add_item == False)
        else:
            prev_sibling = self._get_prev_sibling(lambda add_item: add_item == True)

        if self.additional_item and prev_sibling is not None:
            item_no = self._number_to_letter(self._count_siblings(lambda add_item: add_item == True) +1)
        else:
            self.additional_item = False
            item_no = self._count_siblings(lambda add_item: add_item == False) +1

        if self.is_root_node():
            if config['agenda_numeral_system'] == 'a':
                if self.additional_item:
                    return '%s%s' % (prev_sibling.get_item_no(), item_no)
                else:
                    return '%s' % item_no
            else:
                if self.additional_item:
                    return '%s%s' % (prev_sibling.get_item_no(), item_no)
                else:
                    return '%s' % roman.toRoman(item_no)
        else:
            if not self.additional_item:
                return '%s.%s' % (self.parent.get_item_no(), item_no)
            else:
                if prev_sibling is None:
                    return '%s.%s' % (self.parent.get_item_no(), item_no)
                else:
                    return '%s%s' % (prev_sibling.get_item_no(), item_no)


    def _get_prev_sibling(self, filter_func):
        prev_sibling = self.get_previous_sibling()
        while not prev_sibling is None:
            if prev_sibling.type == self.AGENDA_ITEM and filter_func(prev_sibling.additional_item):
                return prev_sibling
            prev_sibling = prev_sibling.get_previous_sibling()
        return None

    def _get_sibling_no(self):
        """
        :
        """
        prev_sibling = self.get_previous_sibling()
        if self.additional_item and prev_sibling is not None:
            sibling_no = self._count_siblings(lambda add_item: add_item == True) +1
        else:
            sibling_no = self._count_siblings(lambda add_item: add_item == False) +1


    def _count_siblings(self, filter_func):
        sibling_no = 0
        prev_sibling = self.get_previous_sibling()
        while not prev_sibling is None:
            if prev_sibling.type == self.AGENDA_ITEM and filter_func(prev_sibling.additional_item):
                sibling_no += 1
            prev_sibling = prev_sibling.get_previous_sibling()
        return sibling_no


    def _number_to_letter(self, number):
        """
        Returns a lower case letter according to position in alphabet
        E.g. 1 = a, 2 = b, ..., z = 26

        :param number: a number between 1 and 26
        :return: a letter from a to z. None, if number out of range
        """
        return string.lowercase[number - 1] if 0 < number < 27 else None

    def get_title(self):
        """
        return the title of this item.
        """
        if self.related_sid is None:
            if config["agenda_enable_auto_numbering"]:
                if self.type == self.AGENDA_ITEM:
                    return '%s %s %s' % (config['agenda_number_prefix'], self.get_item_no(), self.title)
                else:
                    return '%s' % self.title
            else:
                return self.title
        return self.get_related_slide().get_agenda_title()

    def get_title_supplement(self):
        """
        return a supplement for the title.
        """
        if self.related_sid is None:
            return ''
        try:
            return self.get_related_slide().get_agenda_title_supplement()
        except AttributeError:
            return '(%s)' % self.print_related_type()

    def slide(self):
        if config['presentation_argument'] == 'summary':
            data = {
                'title': self.get_title(),
                'items': self.get_children(),
                'template': 'projector/AgendaSummary.html',
                }
        elif config['presentation_argument'] == 'show_list_of_speakers':
            speakers = Speaker.objects.filter(time=None, item=self.pk).order_by('weight')
            old_speakers = Speaker.objects.filter(item=self.pk).exclude(time=None).order_by('time')
            slice_items = max(0, old_speakers.count()-2)
            data = {'title': self.get_title(),
                    'template': 'projector/agenda_list_of_speaker.html',
                    'speakers': speakers,
                    'old_speakers': old_speakers[slice_items:]}
        elif self.related_sid:
            data = self.get_related_slide().slide()
        else:
            data = {
                'item': self,
                'title': self.get_title(),
                'template': 'projector/AgendaText.html',
                }
        """
        Return a map with all Data for the Slide
        """
        return data

    def set_closed(self, closed=True):
        """
        Changes the closed-status of the item.
        """
        self.closed = closed
        self.save()

    @property
    def weight_form(self):
        """
        Return the WeightForm for this item.
        """
        from openslides.agenda.forms import ItemOrderForm
        try:
            parent = self.parent.id
        except AttributeError:
            parent = 0
        initial = {
            'weight': self.weight,
            'self': self.id,
            'parent': parent,
        }
        return ItemOrderForm(initial=initial, prefix="i%d" % self.id)

    def delete(self, with_children=False):
        """
        Delete the Item.
        """
        if not with_children:
            for child in self.get_children():
                child.move_to(self.parent)
                child.save()
        super(Item, self).delete()
        Item.objects.rebuild()

    def get_absolute_url(self, link='view'):
        """
        Return the URL to this item. By default it is the Link to its
        slide

        link can be:
        * view
        * edit
        * delete
        """
        if link == 'view':
            if self.related_sid:
                return self.get_related_slide().get_absolute_url(link)
            return reverse('item_view', args=[str(self.id)])
        if link == 'edit':
            if self.related_sid:
                return self.get_related_slide().get_absolute_url(link)
            return reverse('item_edit', args=[str(self.id)])
        if link == 'delete':
            return reverse('item_delete', args=[str(self.id)])

    def __unicode__(self):
        return self.get_title()

    class Meta:
        permissions = (
            ('can_see_agenda', ugettext_noop("Can see agenda")),
            ('can_manage_agenda', ugettext_noop("Can manage agenda")),
            ('can_see_orga_items', ugettext_noop("Can see orga items and time scheduling of agenda")),
        )

    class MPTTMeta:
        order_insertion_by = ['weight']


class SpeakerManager(models.Manager):
    def add(self, person, item):
        if self.filter(person=person, item=item, time=None).exists():
            raise OpenSlidesError(_('%(person)s is already on the list of speakers of item %(id)s.') % {'person': person, 'id': item.id})
        weight = (self.filter(item=item).aggregate(
            models.Max('weight'))['weight__max'] or 0)
        return self.create(item=item, person=person, weight=weight + 1)


class Speaker(models.Model):
    """
    Model for the Speaker list.
    """

    objects = SpeakerManager()

    person = PersonField()
    """
    ForeinKey to the person who speaks.
    """

    item = models.ForeignKey(Item)
    """
    ForeinKey to the AgendaItem to which the person want to speak.
    """

    time = models.DateTimeField(null=True)
    """
    Saves the time, when the speaker has spoken. None, if he has not spoken yet.
    """

    weight = models.IntegerField(null=True)
    """
    The sort order of the list of speakers. None, if he has already spoken.
    """

    class Meta:
        permissions = (
            ('can_be_speaker', ugettext_noop('Can put oneself on the list of speakers')),
        )

    def __unicode__(self):
        return unicode(self.person)

    def get_absolute_url(self, link='detail'):
        if link == 'detail' or link == 'view':
            return self.person.get_absolute_url('detail')
        if link == 'delete':
            return reverse('agenda_speaker_delete',
                           args=[self.item.pk, self.pk])

    def speak(self):
        """
        Let the person speak.

        Set the weight to None and the time to now.
        """
        self.weight = None
        self.time = datetime.now()
        self.save()
