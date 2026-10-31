"""Static safety checks and preflight logic for the VPN live smoke harness."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SCRIPT = ROOT / 'scripts' / 'smoke_gserver_vpn_live.py'
spec = importlib.util.spec_from_file_location('vpn_live', SCRIPT)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)
import gserver_vpn as vpn


class VpnLiveSmokeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = SCRIPT.read_text()

    def test_no_secret_output_markers(self):
        for forbidden in ('api.ipify', 'Bearer ', 'PrivateKey', 'secret_token', 'print(data',
                          'print(token', 'PUBLIC_IP='):
            self.assertNotIn(forbidden, self.body)

    def test_envelope_and_core_protection(self):
        for marker in ('GACE_RESULT_BEGIN', 'CORE_NOT_HEALTHY', 'CORE_STORAGE_OTHER_CONTAINERS_UNCHANGED=PASS',
                       'WIREGUARD_CONNECTION=PASS', 'KILL_SWITCH', 'CLOUDFLARE'):
            self.assertIn(marker, self.body)

    def test_uses_real_https_instead_of_local_cached_api(self):
        self.assertIn('https://1.1.1.1/cdn-cgi/trace', self.body)
        self.assertNotIn('127.0.0.1:8000', self.body)

    def test_verifies_resolv_conf_in_container(self):
        self.assertIn('verify_app_resolv_conf', self.body)
        self.assertIn('APP_RESOLV_CONF_APPLIED=PASS', self.body)

    def test_failure_code_not_redacted_to_value(self):
        self.assertIn('LIVE_FAILURE_CODE=', self.body)
        self.assertNotIn('LIVE_FAILURE_DETAIL=', self.body)


class LivePreflightRegion(unittest.TestCase):
    def base_status(self):
        return {
            'docker_access': 'OK',
            'vpn': 'LOCAL_PINNED_IMAGE_PRESENT',
            'app': 'LOCAL_PINNED_IMAGE_PRESENT',
            'cloudflared': 'LOCAL_PINNED_IMAGE_PRESENT',
            'endpoint_cache': 'OK',
            'endpoint_pin_jp': 'NOT_CONFIGURED',
            'endpoint_pin_kr': 'NOT_CONFIGURED',
        }

    def test_jp_run_allows_kr_pin_missing(self):
        status = self.base_status()
        status['endpoint_pin_jp'] = 'CONFIGURED'
        live.validate_live_preflight(status, 'jp')

    def test_jp_run_rejects_missing_jp_pin(self):
        status = self.base_status()
        status['endpoint_pin_kr'] = 'CONFIGURED'
        with self.assertRaises(vpn.VPNError) as error:
            live.validate_live_preflight(status, 'jp')
        self.assertEqual(str(error.exception), 'ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')

    def test_kr_run_allows_jp_pin_missing(self):
        status = self.base_status()
        status['endpoint_pin_kr'] = 'CONFIGURED'
        live.validate_live_preflight(status, 'kr')

    def test_kr_run_rejects_missing_kr_pin(self):
        status = self.base_status()
        status['endpoint_pin_jp'] = 'CONFIGURED'
        with self.assertRaises(vpn.VPNError) as error:
            live.validate_live_preflight(status, 'kr')
        self.assertEqual(str(error.exception), 'ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')


class KillSwitchLogic(unittest.TestCase):
    def test_leak_raises_kill_switch_error(self):
        with mock.patch.object(live, 'tcp_connected', return_value=True):
            with self.assertRaises(vpn.VPNError) as error:
                live.assert_vpn_stop_blocks_publicip('probe')
            self.assertEqual(str(error.exception), 'KILL_SWITCH_LEAK')

    def test_reported_block_is_pass(self):
        with mock.patch.object(live, 'tcp_connected', return_value=False):
            live.assert_vpn_stop_blocks_publicip('probe')

    def test_exec_failure_is_failure_not_blocked_pass(self):
        for exc in (live.apps.AppError('DOCKER_COMMAND_FAILED'), vpn.VPNError('APP_PROBE_REPORT_INVALID')):
            with self.subTest(error=str(exc)), mock.patch.object(live, 'tcp_connected', side_effect=exc):
                with self.assertRaises(type(exc)):
                    live.assert_vpn_stop_blocks_publicip('probe')

    def test_source_does_not_swallow_leak_in_broad_except(self):
        body = SCRIPT.read_text()
        block = body[body.find("phase = 'KILL_SWITCH'"):body.find("phase = 'CLOUDFLARE'")]
        self.assertIn('assert_vpn_stop_blocks_publicip', block)
        self.assertNotIn('except (apps.AppError, vpn.VPNError)', block)


class LiveFailureDetail(unittest.TestCase):
    def test_vpn_error_code_preserved(self):
        exc = vpn.VPNError('ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')
        self.assertEqual(live.live_failure_detail(exc), 'ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')

    def test_unstructured_message_sanitized(self):
        token = 'x' * 40
        detail = live.live_failure_detail(RuntimeError('boom ' + token))
        self.assertNotIn(token, detail)
        self.assertIn('<value>', detail)


class RealNetworkEvidence(unittest.TestCase):
    def test_https_checks_region_and_public_ipv4_without_printing_ip(self):
        for report, expected in (
            ({'uid':65534,'ip':'1.1.1.1','country':'JP'}, None),
            ({'uid':65534,'ip':'1.1.1.1','country':'KR'}, 'EGRESS_COUNTRY_MISMATCH'),
            ({'uid':65534,'ip':'127.0.0.1','country':'JP'}, 'EGRESS_IP_INVALID'),
            ({'uid':0,'ip':'1.1.1.1','country':'JP'}, 'EGRESS_IP_INVALID'),
            ({'uid':65534,'ip':'::1','country':'JP'}, 'EGRESS_IP_INVALID'),
            ({'uid':65534,'ip':None,'country':'JP'}, 'EGRESS_IP_INVALID')):
            with self.subTest(report=report), mock.patch.object(live,'app_json',return_value=report) as probe:
                if expected:
                    with self.assertRaisesRegex(vpn.VPNError, expected):
                        live.https_exit('app',live.TRACE_URLS[0],'jp')
                else:
                    self.assertEqual(live.https_exit('app',live.TRACE_URLS[0],'jp'),'1.1.1.1')
                code=probe.call_args.args[1]
                compile(code,'<https-probe>','exec')
                self.assertIn('ProxyHandler({})',code)
                self.assertIn('NoRedirect()',code)
                self.assertNotIn('unverified',code)
                self.assertIn('r.read(4097)',code)

    def test_tcp_requires_explicit_valid_report(self):
        for report in ({}, {'uid':0,'state':'blocked'}, {'uid':65534,'state':'error'}):
            with mock.patch.object(live,'app_json',return_value=report):
                with self.assertRaisesRegex(vpn.VPNError,'APP_PROBE_REPORT_INVALID'):
                    live.tcp_connected('app',live.TCP_CANARY,443)
        for state in ('connected','blocked'):
            with mock.patch.object(live,'app_json',return_value={'uid':65534,'state':state}) as probe:
                self.assertEqual(live.tcp_connected('app',live.TCP_CANARY,443), state=='connected')
                compile(probe.call_args.args[1],'<tcp-probe>','exec')

    def test_tcp_os_errors_are_not_automatically_blocked(self):
        import contextlib,errno,io,json,socket
        for error,accepted in ((TimeoutError(),True),(OSError(errno.ENETUNREACH,'unreachable'),True),
                               (ConnectionRefusedError(errno.ECONNREFUSED,'refused'),False),
                               (OSError(errno.EBADF,'invalid descriptor'),False)):
            with self.subTest(error=type(error).__name__), \
                 mock.patch.object(live,'app_json',return_value={'uid':65534,'state':'blocked'}) as probe:
                live.tcp_connected('app',live.TCP_CANARY,443)
                code=probe.call_args.args[1]
            stream=io.StringIO()
            with mock.patch.object(socket,'socket') as sock, mock.patch('os.getuid',return_value=65534), contextlib.redirect_stdout(stream):
                sock.return_value.connect.side_effect=error
                if accepted:
                    exec(code,{})
                    self.assertEqual(json.loads(stream.getvalue())['state'],'blocked')
                else:
                    with self.assertRaises(OSError): exec(code,{})

    def test_app_exec_errors_and_malformed_json_never_pass(self):
        for value in ('','not json','[]','null'):
            with mock.patch.object(live,'docker',return_value=value):
                with self.assertRaisesRegex(vpn.VPNError,'APP_PROBE_REPORT_INVALID'):
                    live.app_json('app','probe')
        with mock.patch.object(live,'docker',side_effect=live.apps.AppError('DOCKER_COMMAND_FAILED')):
            with self.assertRaises(live.apps.AppError): live.app_json('app','probe')

    def test_kernel_wireguard_identity_and_counters_are_required(self):
        import copy,json
        valid={'inode':10,'link':[{'ifname':'tun0','ifindex':7,'flags':['UP'],
               'linkinfo':{'info_kind':'wireguard'},'stats64':{'rx':{'bytes':10},'tx':{'bytes':20}}}]}
        changes=[None,'tun','missing','negative','boolean','down','duplicate']
        for change in changes:
            report=copy.deepcopy(valid)
            link=report['link'][0]
            if change=='tun': link['linkinfo']['info_kind']='tun'
            if change=='missing': del link['stats64']
            if change=='negative': link['stats64']['rx']['bytes']=-1
            if change=='boolean': link['stats64']['rx']['bytes']=True
            if change=='down': link['flags']=[]
            if change=='duplicate': report['link']*=2
            with self.subTest(change=change), \
                 mock.patch.object(live,'docker',return_value=json.dumps([{'State':{'Running':True,'Pid':1234}}])) as command, \
                 mock.patch.object(live.vpn,'namespace_guard',return_value=report) as guard:
                if change is None:
                    self.assertEqual(live.wireguard_state('vpn'),((10,7),10,20))
                else:
                    with self.assertRaisesRegex(vpn.VPNError,'WIREGUARD_KERNEL_TELEMETRY_INVALID'):
                        live.wireguard_state('vpn')
                guard.assert_called_once_with(1234,link=True)
                self.assertTrue(all(c.args==('inspect','vpn') for c in command.call_args_list))

    def test_kernel_telemetry_rejects_container_restart(self):
        import json
        states=[json.dumps([{'State':{'Running':True,'Pid':pid}}]) for pid in (1234,5678)]
        with mock.patch.object(live,'docker',side_effect=states), \
             mock.patch.object(live.vpn,'namespace_guard',return_value={'inode':10}):
            with self.assertRaisesRegex(vpn.VPNError,'VPN_NAMESPACE_CHANGED'):
                live.wireguard_state('vpn')

    def report(self,udp=0,tcp=0,inode=10):
        return {'inode':inode,'nft':{'nftables':[{'rule':{'comment':'gserver_dns_'+proto,
            'expr':[{'counter':{'packets':count,'bytes':count*40}},{'drop':None}]}}
            for proto,count in (('udp',udp),('tcp',tcp))]}}

    def test_dns_requires_both_observed_drop_counters(self):
        for udp,tcp,accepted in ((1,1,True),(1,0,False),(0,1,False),(0,0,False)):
            with self.subTest(udp=udp,tcp=tcp), \
                 mock.patch.object(live,'app_guard',side_effect=[self.report(),self.report(udp,tcp)]), \
                 mock.patch.object(live,'tcp_connected',return_value=False), \
                 mock.patch.object(live,'app_json',side_effect=[{'uid':65534,'sent':True},{'disabled':'1'}]):
                if accepted: live.verify_network_guards('app')
                else:
                    with self.assertRaisesRegex(vpn.VPNError,'DNS_GUARD_DROP_NOT_OBSERVED'):
                        live.verify_network_guards('app')

    def test_ipv6_must_be_disabled_and_public_connect_fail(self):
        for disabled,connect in (('0',False),('1',True)):
            with mock.patch.object(live,'app_guard',side_effect=[self.report(),self.report(1,1)]), \
                 mock.patch.object(live,'tcp_connected',side_effect=[False,connect]), \
                 mock.patch.object(live,'app_json',side_effect=[{'uid':65534,'sent':True},{'disabled':disabled}]):
                with self.assertRaisesRegex(vpn.VPNError,'IPV6_NOT_BLOCKED'):
                    live.verify_network_guards('app')

    def test_stopped_app_is_failure_and_changed_namespace_is_failure(self):
        with mock.patch.object(live,'docker',return_value='[{"State":{"Running":false,"Pid":0}}]'):
            with self.assertRaisesRegex(vpn.VPNError,'APP_NOT_RUNNING'): live.app_guard('app')
        with self.assertRaisesRegex(vpn.VPNError,'APP_NAMESPACE_OR_GUARD_CHANGED'):
            live.unchanged_guard(self.report(),self.report(inode=11))

    def test_cloudflare_credential_is_refused_before_docker_mutation(self):
        import contextlib,io
        with mock.patch.dict(live.os.environ,{'GSERVER_CLOUDFLARED_CREDENTIAL':'unused'}), \
             mock.patch.object(live,'inventory') as inventory, \
             mock.patch.object(live,'docker') as docker, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(live.main(),1)
        inventory.assert_not_called();docker.assert_not_called()
        self.assertIn('CLOUDFLARE_REQUIRES_SEPARATE_AUTHORIZED_GATE',output.getvalue())
        self.assertIn('ACCEPTANCE_CLOUDFLARE=NOT_RUN',output.getvalue())


class LiveLifecycleEvidence(unittest.TestCase):
    def exercise(self, *, tcp=(True,False), transfer=True, https_fail=False):
        import contextlib,io
        report={'inode':10,'nft':{'nftables':[]}}
        def docker(*args):
            if args[0]=='inspect': return '[{"State":{"Health":{"Status":"healthy"}}}]'
            return ''
        output=io.StringIO()
        with mock.patch.dict(live.os.environ,{'GSERVER_VPN_REGION':'jp','GSERVER_CLOUDFLARED_CREDENTIAL':''}), \
             mock.patch.object(live,'inventory',return_value={'existing':'same'}), \
             mock.patch.object(live,'storage',return_value=['same']), \
             mock.patch.object(live,'docker',side_effect=docker) as command, \
             mock.patch.object(live,'resolve_images',return_value=('app','vpn',None)), \
             mock.patch.object(live.vpn,'profile'),mock.patch.object(live.vpn,'endpoint_pins',return_value={'jp':'pin'}), \
             mock.patch.object(live.vpn,'preflight',return_value={'endpoint_pin_jp':'CONFIGURED'}), \
             mock.patch.object(live.vpn,'render',return_value={'project':'gace-vpn-'+'a'*16}), \
             mock.patch.object(live.vpn,'start'),mock.patch.object(live,'service_container',side_effect=['app-id','vpn-id']), \
             mock.patch.object(live,'verify_app_resolv_conf'),mock.patch.object(live,'verify_network_guards'), \
             mock.patch.object(live,'wireguard_state',side_effect=[('peer',10,20),('peer',11 if transfer else 10,21)]), \
             mock.patch.object(live,'https_exit',side_effect=live.apps.AppError('HTTP_FAILED') if https_fail else None,return_value='1.1.1.1'), \
             mock.patch.object(live,'tcp_connected',side_effect=tcp), \
             mock.patch.object(live,'app_guard',return_value=report),contextlib.redirect_stdout(output):
            result=live.main()
        calls=command.call_args_list
        self.assertEqual(len([c for c in calls if 'down' in c.args]),1)
        self.assertIn('CORE_STORAGE_OTHER_CONTAINERS_UNCHANGED=PASS',output.getvalue())
        return result,output.getvalue(),calls

    def test_full_probe_success_still_not_cloudflare_or_performance_acceptance(self):
        code,output,_=self.exercise()
        self.assertEqual(code,0)
        self.assertIn('VPN_KILL_SWITCH_PUBLIC_TCP=PASS',output)
        self.assertIn('ACCEPTANCE_CLOUDFLARE=NOT_RUN',output)
        self.assertIn('PERFORMANCE=NOT_VERIFIED',output)

    def test_positive_control_failure_never_stops_vpn_or_passes(self):
        code,output,calls=self.exercise(tcp=[False])
        self.assertEqual(code,1)
        self.assertIn('KILL_SWITCH_POSITIVE_CONTROL_FAILED',output)
        self.assertFalse(any('stop' in c.args for c in calls))

    def test_leak_is_failure_and_cleanup_still_runs(self):
        code,output,_=self.exercise(tcp=[True,True])
        self.assertEqual(code,1)
        self.assertIn('KILL_SWITCH_LEAK',output)
        self.assertNotIn('VPN_KILL_SWITCH_PUBLIC_TCP=PASS',output)

    def test_exec_failure_during_kill_switch_is_failure(self):
        code,output,_=self.exercise(tcp=[True,live.apps.AppError('DOCKER_COMMAND_FAILED')])
        self.assertEqual(code,1)
        self.assertIn('LIVE_FAILURE_CODE=DOCKER_COMMAND_FAILED',output)
        self.assertNotIn('VPN_KILL_SWITCH_PUBLIC_TCP=PASS',output)

    def test_no_transfer_or_https_failure_never_claims_wireguard_pass(self):
        for kwargs in ({'transfer':False},{'https_fail':True}):
            with self.subTest(kwargs=kwargs):
                code,output,_=self.exercise(**kwargs)
                self.assertEqual(code,1)
                self.assertNotIn('WIREGUARD_CONNECTION=PASS',output)


if __name__ == '__main__':
    unittest.main()
