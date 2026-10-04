"""Capture the fictional one-minute case in the actual app, using a test DB."""
import json
import os
import secrets
from datetime import timedelta
from time import perf_counter

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from portal.engine.calculator import compare, saved_decision, simulate
from portal.models import AnalysisRun, Company, Membership, Scenario
from scripts.video.capture import POINTER
from scripts.video.short_case import OUT, short_case


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class ShortFilmCapture(StaticLiveServerTestCase):
    def test_capture_verified_example(self):
        from playwright.sync_api import sync_playwright, expect
        data = short_case()
        expected = compare(data)
        prepared = json.loads((OUT / 'prepared-case.json').read_text(encoding='utf-8'))
        self.assertEqual(prepared['inputs'], data.to_dict())
        self.assertEqual(prepared['results'], expected)
        best = expected['strategies'][0]
        self.assertGreater(best['rows'][0]['alternative_t'], 0)
        self.assertGreater(best['actions']['electricity_mwh'], 0)
        self.assertFalse(best['actions']['pooling_used'])
        self.assertEqual(best['penalty_cost'], 0)
        for option in expected['strategies']:
            replay = simulate(data, [saved_decision(d) for d in option['decisions']], option['use_pool'])
            self.assertAlmostEqual(option['npv'], replay['npv'], places=6)
        company = Company.objects.create(name='Illustrative planning case', status='active',
            access_until=timezone.localdate() + timedelta(days=30))
        password = secrets.token_urlsafe(24)
        user = get_user_model().objects.create_user('short_demo', password=password)
        Membership.objects.create(company=company, user=user, role='analyst')
        case = Scenario.objects.create(company=company, created_by=user, inputs=data.to_dict(),
            name='Demo Aurora · 2026')
        raw = OUT / 'raw'
        raw.mkdir(parents=True, exist_ok=True)
        errors, shots = [], []
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, channel=os.environ.get('PLAYWRIGHT_CHANNEL', 'msedge'))
            context = browser.new_context(viewport={'width': 1600, 'height': 1000},
                record_video_dir=str(raw), record_video_size={'width': 1600, 'height': 1000})
            context.add_init_script(POINTER)
            page = context.new_page()
            origin = perf_counter()
            page.set_default_timeout(60000)
            page.emulate_media(reduced_motion='reduce')
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('login'))
            page.get_by_label('Username').fill(user.username)
            page.get_by_label('Password').fill(password)
            page.get_by_role('button', name='Sign in securely').click()

            def panel(title):
                return page.locator('details[data-disclosure]').filter(has=page.get_by_role('heading', name=title, exact=True))

            def save(key, target):
                target.scroll_into_view_if_needed()
                page.mouse.move(5, 5)
                page.wait_for_timeout(750)  # Let the filming click halo finish.
                target.screenshot(path=str(raw / f'{key}.png'))

            page.goto(self.live_server_url + reverse('vessel_edit', args=[case.pk, 0]))
            expect(page.locator('details[data-disclosure][open]')).to_have_count(0)
            page.screenshot(path=str(raw / 'compact-vessel.png'), full_page=True)
            consumption = panel('Consumption & voyage mix')
            consumption.locator('summary').click()
            save('consumption', page.locator('.consumption-table-scroll'))
            self.assertEqual(page.locator('[data-sea-fuel-row]').count(), 5)
            fuel = panel('Fuel switching boundaries')
            fuel.locator('summary').click()
            expect(page.locator('#id_alternative')).to_have_value('FAME')
            expect(page.locator('#id_compatible')).to_be_checked()
            save('fame', fuel)
            shore = panel('Shore power & investment assumptions')
            shore.locator('summary').click()
            expect(page.locator('#id_ops_ready')).to_be_checked()
            expect(page.locator('#id_ops_capex')).to_have_value('0')
            save('shore', shore)
            # Record an actual control action, preserving the prepared inputs.
            page.locator('#id_ops_ready').uncheck()
            start = perf_counter() - origin
            page.wait_for_timeout(600)
            page.locator('#id_ops_ready').check()
            page.wait_for_timeout(1800)
            shots.append(dict(key='enable-shore', start=start, end=perf_counter()-origin))
            page.get_by_role('button', name='Save vessel').click()
            expect(page.get_by_role('heading', name='Every ship keeps its own balance.')).to_be_visible()
            start = perf_counter() - origin
            page.get_by_role('button', name='Compare strategies').click()
            expect(page.locator('.recommendation')).to_be_visible()
            page.wait_for_timeout(1600)
            shots.append(dict(key='compare', start=start, end=perf_counter()-origin))
            save('recommendation', page.locator('.recommendation'))
            save('metrics', page.locator('.metric-grid'))
            save('strategies', page.locator('.strategy-panel'))
            save('actions', page.locator('[data-strategy-explanation]'))
            for option in expected['strategies']:
                cost = f"{option['npv']:,.0f}"
                self.assertIn(cost, page.locator('.strategy-list').inner_text())
            with page.expect_download() as download:
                page.get_by_role('link', name='Audit file').click()
            download.value.save_as(str(OUT / 'demo-audit.json'))
            audit = json.loads((OUT / 'demo-audit.json').read_text(encoding='utf-8'))
            self.assertEqual(audit['results'], expected)
            video = page.video
            wall = perf_counter()-origin
            context.close()
            video.save_as(str(raw / 'walkthrough.webm'))
            browser.close()
        self.assertEqual(errors, [])
        case.refresh_from_db()
        self.assertEqual(case.inputs, data.to_dict())
        run = AnalysisRun.objects.get(scenario=case)
        self.assertEqual(run.results, expected)
        self.assertEqual(run.inputs, data.to_dict())
        (OUT / 'capture.json').write_text(json.dumps(dict(scenes=shots, recording_wall_seconds=wall,
            checked=['prepared inputs', 'saved inputs', 'engine replay', 'report costs', 'JSON audit', 'no page errors']), indent=2), encoding='utf-8')
        print('Verified app captures and exported audit: passed', flush=True)
