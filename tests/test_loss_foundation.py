"""Evidence-based adjustment, fixed denominator, and separate causal covariates."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
import yfinance as yf

from src.adjustment import adjust_paired, verify_adjustment
from src.collection_health import collection_health, failure_category
from src.data import clean_data
from src.data_audit import preserve_raw
from src.loss_diagnostics import diagnose_losses, path_metrics
from src.preservation import write_record
from test_prospective import enrolled


def paired():
    # Retained ABBV paired observation reproduces a real binary64 round-trip.
    return pd.DataFrame({'Open':[71.,72.], 'High':[73.06,73.], 'Low':[70.,70.],
        'Close':[73.06,72.], 'Adj Close':[50.34667205810547,60.], 'Volume':[100,200]},
        index=pd.to_datetime(['2017-07-19','2017-07-20']))


def round_trip_fixture():
    # Deterministically find a finite positive exact tie with one-step round trip.
    frame = paired()
    for close in [73.05999755859375,73.06,100.,57.13]:
        for adjusted in [50.34667205810547,50.123456789,31.737735748291016,61.23]:
            if close*(adjusted/close)<adjusted:
                frame.loc[frame.index[0],['High','Close']]=close
                frame.loc[frame.index[0],'Adj Close']=adjusted
                return frame
    raise AssertionError('Fixture must reproduce round-trip defect')


def test_equality_fix_preserves_valid_rows_and_close():
    raw=round_trip_fixture()
    old=yf.utils.auto_adjust(raw.copy())
    with pytest.raises(ValueError,match='Malformed'):
        clean_data(old,'ABBV')
    original=raw.copy(deep=True)
    new, changes=adjust_paired(raw,'ABBV')
    assert len(changes)==1
    assert new.High.iloc[0]==new.Close.iloc[0]
    assert_frame_equal(new.iloc[1:],old.iloc[1:])
    assert new.Close.equals(old.Close)
    assert_frame_equal(raw,original)
    clean_data(new,'ABBV')


@pytest.mark.parametrize('column,value', [('High',60.),('Low',90.),('Open',90.),('Close',90.),
    ('Volume',-1),('Adj Close',np.nan),('Adj Close',-1),('Adj Close',np.inf)])
def test_genuine_bad_paired_input_rejected(column,value):
    raw=paired();raw.loc[raw.index[0],column]=value
    with pytest.raises(ValueError):
        adjust_paired(raw,'ABBV')


def test_one_step_raw_malformed_is_not_accepted():
    raw=paired()
    raw.loc[raw.index[0],'Close']=np.nextafter(raw.High.iloc[0],np.inf)
    with pytest.raises(ValueError,match='Malformed'):
        adjust_paired(raw,'ABBV')


def test_identity_mismatch_rejected():
    raw=paired();raw['ticker']='WRONG'
    with pytest.raises(ValueError,match='ticker other'):
        adjust_paired(raw,'ABBV')


def test_paired_evidence_replay_and_future_rows(tmp_path):
    raw=round_trip_fixture(); adjusted,changes=adjust_paired(raw,'ABBV')
    item={'ticker':'ABBV','paired_sha256':preserve_raw(tmp_path,raw)['raw_sha256'],
          **preserve_raw(tmp_path,adjusted),'adjustment_policy':'raw-boundary-equality-v1',
          'adjustment_changes':changes}
    verify_adjustment(tmp_path,item)
    missing=deepcopy(item);missing.pop('paired_sha256')
    with pytest.raises(ValueError,match='evidence missing'):
        verify_adjustment(tmp_path,missing)
    changed=deepcopy(item);changed['adjustment_changes'][0]['after']+=1
    with pytest.raises(ValueError,match='evidence'):
        verify_adjustment(tmp_path,changed)
    extended=pd.concat([raw,raw.iloc[-1:].set_axis(pd.to_datetime(['2017-07-21']))])
    extended.iloc[-1,extended.columns.get_loc('Adj Close')]=50
    future,_=adjust_paired(extended,'ABBV')
    assert_frame_equal(future.iloc[:2],adjusted)


@pytest.mark.parametrize('error,category', [
    ('ValueError: Malformed OHLC','malformed_ohlc'), ('stale prices','stale_incomplete'),
    ('Duplicate rows','duplicate'),('Missing required data','missing'),
    ('timestamp invalid','schema_numeric'), ('RuntimeError: download failed','acquisition'),
    ('Input contains ticker other','identity'),('unexplained','unavailable'), (None,'not_collected')])
def test_failure_categories(error,category):
    assert failure_category(error)==category


def test_health_retains_95_and_does_not_promote_partial(enrolled):
    root,_,_=enrolled
    h=collection_health(root,as_of='2026-10-06T12:00:00Z')
    assert len(h['sessions'])==1
    row=h['sessions'][0]
    assert row['requested']==95
    assert row['successful']+row['failed']==95
    assert not h['gate']['satisfied']
    assert row['failed']==93
    assert len(row['failures'])==93
    same=collection_health(root,as_of='2026-10-06T12:00:00Z')
    assert h==same


def path_fixture():
    signal=pd.Series({'close':100.,'atr_pct_14':.02})
    path=pd.DataFrame({'open':[100.,90.]+[100.]*18,'high':[101.,95.]+[105.]*18,
                       'low':[99.,89.]+[99.]*18,'close':[100.,94.]+[103.]*18})
    trade=pd.Series({'exit_reason':'stop_loss','fill_type':'open','holding_bars':2,
                     'net_return':-.101,'mae':-.10,'mfe':.01,'exit_price':90.})
    return signal,path,trade


def test_mae_atr_gap_and_later_recovery():
    signal,path,trade=path_fixture()
    m=path_metrics(signal,path,trade)
    assert m['full_10bar_mae']==pytest.approx(-.11)
    assert m['mae_atr']==pytest.approx(5.5)
    assert m['full_10bar_mfe']==pytest.approx(.05)
    assert m['worst_overnight_gap']==pytest.approx(-.10)
    assert m['gap_stop']
    assert m['recovered_after_stop_bar']==3
    assert m['recovery_category']=='deep_drawdown_with_recovery'


def test_same_bar_recovery_not_called_after_stop():
    signal,path,trade=path_fixture()
    path.loc[1,'close']=103.
    path.loc[2:,'close']=90.
    assert path_metrics(signal,path,trade)['recovered_after_stop_bar'] is None


def test_recovery_censoring_and_invalid_atr():
    signal,path,trade=path_fixture();signal['atr_pct_14']=np.nan
    m=path_metrics(signal,path.iloc[:10],trade)
    assert np.isnan(m['mae_atr'])
    assert m['recovery_category']=='censored_20bar'
    assert np.isnan(m['net_return_at_20bar'])


def test_loss_diagnostics_refuse_prospective_cutoff():
    with pytest.raises(ValueError,match='prospective'):
        diagnose_losses(pd.DataFrame(),pd.DataFrame(),cutoff='2026-10-06')


def test_historical_future_mutation_cannot_change_diagnostics():
    from src.loss_diagnostics import COVARIATES
    signal,path,trade=path_fixture()
    obs=pd.concat([pd.DataFrame({'open':[100.],'high':[101.],'low':[99.],'close':[100.]}),path],ignore_index=True)
    obs['timestamp']=pd.bdate_range('2025-01-02',periods=len(obs))
    obs['ticker']='ABT';obs['fold']='2025';obs['regime']='above';obs['dip_event_v1']=False
    obs.loc[0,'dip_event_v1']=True
    for key in COVARIATES:
        obs[key]=.02
    for key in ['dip_drawdown_component','dip_price_zscore_component','dip_low_proximity_component','dip_relative_weakness_component']:
        obs[key]=True
    trades=pd.DataFrame([trade.to_dict()|{'ticker':'ABT','fold':'2025','timestamp':obs.timestamp.iloc[0],
                                        'status':'completed','mode':'independent'}])
    first=diagnose_losses(obs,trades,cutoff='2026-10-05')
    future=obs.iloc[-1:].copy();future['timestamp']=pd.Timestamp('2026-10-06')
    future[['open','high','low','close']]*=10
    second=diagnose_losses(pd.concat([obs,future]),trades,cutoff='2026-10-05')
    for key in first:
        assert_frame_equal(first[key],second[key])


def test_paired_capture_retains_failed_raw_and_does_not_repair_legacy(tmp_path,monkeypatch):
    from src import paper_archive as archive, adjustment
    from src.data import PROVENANCE_KEY
    from src.preservation import get_object
    raw=round_trip_fixture()
    raw.attrs[PROVENANCE_KEY]={'ticker':'ABBV','schema_version':1,'interval':'1d','provider':'test',
                             'retrieved_at':'2026-10-07T11:00:00Z'}
    monkeypatch.setattr(adjustment,'download_paired',lambda *a,**k:raw.copy())
    result=archive.capture_input(tmp_path,'ABBV',config=archive.load_protocol(),session='2026-10-06')
    assert result['status']=='available'
    verify_adjustment(tmp_path,result)
    legacy=yf.utils.auto_adjust(raw.copy())
    monkeypatch.setattr(archive,'download_raw_data',lambda *a,**k:legacy.copy())
    old=archive.capture_input(tmp_path,'ABBV',config=archive.load_protocol(),session='2026-10-05')
    assert old['status']=='unavailable'
    assert 'paired_sha256' not in old
    original=get_object(tmp_path,old['raw_sha256'])
    raw.loc[raw.index[0],'Close']=200.
    bad=archive.capture_input(tmp_path,'ABBV',config=archive.load_protocol(),session='2026-10-06')
    assert bad['status']=='unavailable'
    assert bad['paired_sha256']
    get_object(tmp_path,bad['paired_sha256'])
    assert get_object(tmp_path,old['raw_sha256'])==original


def test_low_boundary_round_trip_and_nonadjacent_adjustment_rejection(monkeypatch):
    raw=paired()
    # Exact operands from the retained DUK 2017-06-30 paired observation.
    raw.loc[raw.index[0],['Open','High','Low','Close','Adj Close']]=[
        84.1500015258789,84.41999816894531,83.58999633789062,83.58999633789062,57.55463409423828]
    result,changes=adjust_paired(raw,'ABBV')
    assert changes[0]['field']=='Low'
    assert result.Low.iloc[0]==result.Close.iloc[0]
    actual=yf.utils.auto_adjust
    def corrupt(frame):
        f=actual(frame)
        f.loc[f.index[0],'Low']=f.Close.iloc[0]+.01
        return f
    monkeypatch.setattr(yf.utils,'auto_adjust',corrupt)
    with pytest.raises(ValueError,match='boundary evidence'):
        adjust_paired(raw,'ABBV')


def test_recurring_failures_and_interrupted_sessions_keep_denominator(tmp_path,monkeypatch):
    from src import collection_health as health
    from src.sessions import session_facts
    names=health.load_protocol()['universe']
    for day in ['2026-10-05','2026-10-06']:
        directory=tmp_path/'runs'/day
        write_record(directory/'intent.json',{'run_id':day,'mode':'collect','corrects':None,
                                            'session':day,'calendar':session_facts(day)})
        for ticker in names:
            write_record(directory/'inputs'/f'{ticker}.json',{'ticker':ticker,'status':'unavailable',
                                                           'error':'ValueError: Malformed OHLC'})
    monkeypatch.setattr(health,'verify_run',lambda *a,**k:{'status':'interrupted'})
    result=health.collection_health(tmp_path,as_of='2026-10-07T15:00:00Z')
    assert len(result['sessions'])==2
    assert all(r['requested']==r['failed']==95 for r in result['sessions'])
    assert all(r['sessions']==2 for r in result['recurring_failures'])
    assert not result['gate']['satisfied']
