import json
from datetime import timedelta

import pytest
from django.utils.timezone import now

from pretix.base.models import (
    Event, EventPermission, Item, ItemVariation, Order, OrderPosition,
    Organizer, User,
)


@pytest.fixture
def env():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o, name='Dummy', slug='dummy',
        date_from=now(), plugins='pretix.plugins.banktransfer'
    )
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    EventPermission.objects.create(user=user, event=event)
    shirt = Item.objects.create(event=event, name='T-Shirt', default_price=12)
    shirt_red = ItemVariation.objects.create(item=shirt, default_price=14, value="Red")
    ItemVariation.objects.create(item=shirt, value="Blue")
    ticket = Item.objects.create(event=event, name='Ticket', default_price=23)
    o1 = Order.objects.create(
        code='FOO', event=event, status=Order.STATUS_PENDING,
        datetime=now(), expires=now() + timedelta(days=10),
        total=0, payment_provider='banktransfer'
    )
    op1 = OrderPosition.objects.create(
        order=o1, item=shirt, variation=shirt_red,
        price=12, attendee_name=None
    )
    op2 = OrderPosition.objects.create(
        order=o1, item=ticket,
        price=23, attendee_name="Peter"
    )
    return event, user, o1, op1, op2


@pytest.mark.django_db
@pytest.mark.xfail(reason="Not working since a30fa2c but currently not in use anyway")
def test_pretixdroid(client, env):
    client.login(email='dummy@dummy.dummy', password='dummy')
    client.get('/control/event/%s/%s/pretixdroid/' % (env[0].organizer.slug, env[0].slug))
    key1 = env[0].settings.get('pretixdroid_key')
    assert key1
    client.get('/control/event/%s/%s/pretixdroid/?flush_key=1' % (env[0].organizer.slug, env[0].slug))
    env[0].settings._flush()
    key = env[0].settings.get('pretixdroid_key')
    assert key and key1 != key
    response = client.get('/pretixdroid/api/%s/%s/?key=%s' % (env[0].organizer.slug, env[0].slug, key1))
    assert response.status_code == 403
    response = client.get('/pretixdroid/api/%s/%s/?key=%s' % (env[0].organizer.slug, env[0].slug, key))
    assert response.status_code == 200
    jdata = json.loads(response.content.decode("utf-8"))
    assert jdata['version'] == 1
    assert len(jdata['data']) == 0
    env[2].status = Order.STATUS_PAID
    env[2].save()
    response = client.get('/pretixdroid/api/%s/%s/?key=%s' % (env[0].organizer.slug, env[0].slug, key))
    assert response.status_code == 200
    jdata = json.loads(response.content.decode("utf-8"))
    assert jdata['version'] == 1
    assert len(jdata['data']) == 2
    assert {"id": env[3].id, "variation": "Red", "attendee_name": None, "item": "T-Shirt"} in jdata['data']
    assert {"id": env[4].id, "variation": None, "attendee_name": "Peter", "item": "Ticket"} in jdata['data']
