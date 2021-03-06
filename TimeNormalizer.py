#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2017/11/20 16:39
# @Author  : zhm
# @File    : TimeNormalizer.py
# @Software: PyCharm
import pickle
import regex as re
import arrow
import json
import os

from src.ner.chinese_time_normalizer.StringPreHandler import StringPreHandler
from src.ner.chinese_time_normalizer.TimePoint import TimePoint
from src.ner.chinese_time_normalizer.TimeUnit import TimeUnit

# 时间表达式识别的主要工作类
class TimeNormalizer:
    def __init__(self, isPreferFuture=True):
        self.isPreferFuture = isPreferFuture
        self.pattern, self.holi_solar, self.holi_lunar = self.init()

    # 这里对一些不规范的表达做转换
    def _filter(self, input_query):
        # 这里对于下个周末这种做转化 把个给移除掉
        input_query = StringPreHandler.numberTranslator(input_query)

        rule = u"[0-9]月[0-9]"
        pattern = re.compile(rule)
        match = pattern.search(input_query)
        if match != None:
            index = input_query.find('月')
            rule = u"日|号"
            pattern = re.compile(rule)
            match = pattern.search(input_query[index:])
            if match == None:
                rule = u"[0-9]月[0-9]+"
                pattern = re.compile(rule)
                match = pattern.search(input_query)
                if match != None:
                    end = match.span()[1]
                    input_query = input_query[:end] + '号' + input_query[end:]

        rule = u"月"
        pattern = re.compile(rule)
        match = pattern.search(input_query)
        if match == None:
            input_query = input_query.replace('个', '')

        input_query = input_query.replace('中旬', '15号')
        input_query = input_query.replace('傍晚', '午后')
        input_query = input_query.replace('大年', '')
        input_query = input_query.replace('五一', '劳动节')
        input_query = input_query.replace('白天', '早上')
        input_query = input_query.replace('：', ':')
        return input_query

    def init(self):
        fpath = os.path.dirname(__file__) + '/resource/reg.pkl'
        try:
            with open(fpath, 'rb') as f:
                pattern = pickle.load(f)
        except:
            with open(os.path.dirname(__file__) + '/resource/regex.txt', 'r', encoding="utf-8") as f:
                content = f.read()
            p = re.compile(content)
            with open(fpath, 'wb') as f:
                pickle.dump(p, f)
            with open(fpath, 'rb') as f:
                pattern = pickle.load(f)
        with open(os.path.dirname(__file__) + '/resource/holi_solar.json', 'r', encoding='utf-8') as f:
            holi_solar = json.load(f)
        with open(os.path.dirname(__file__) + '/resource/holi_lunar.json', 'r', encoding='utf-8') as f:
            holi_lunar = json.load(f)
        return pattern, holi_solar, holi_lunar

    def parse(self, target, timeBase=arrow.now()):
        """
        TimeNormalizer的构造方法，timeBase取默认的系统当前时间
        :param timeBase: 基准时间点
        :param target: 待分析字符串
        :return: 时间单元数组
        """
        self.isTimeSpan = False
        self.isHoliday = False
        self.invalidSpan = False
        self.timeSpan = ''
        self.target = self._filter(target)
        self.timeBase = arrow.get(timeBase).format('YYYY-M-D-H-m-s')
        self.nowTime = timeBase
        self.oldTimeBase = self.timeBase
        self.__preHandling()
        self.timeToken = self.__timeEx()
        dic = {}
        res = self.timeToken

        dic['raw'] = ''
        for r in res:
            dic['raw'] += r.exp_time + ','
        dic['raw'] = dic['raw'].strip(',')

        if re.match(r'(这|近|前|(最近))([零一二三四五六七八九十百千万]+|\d+)(天|周|年|月)',dic['raw']):
            shift = res[0].tp_origin.tunit
            for t in range(len(shift)):
                if shift[t] == -1:
                    shift[t] = 0
            stop_time = arrow.get(timeBase)
            start_time = stop_time.shift(years=-shift[0],months=-shift[1],days=-shift[2])
            start_time = [start_time.year,start_time.month,start_time.day,-1,-1,-1]
            stop_time = [stop_time.year,stop_time.month,stop_time.day,-1,-1,-1]
            dic['type'] = 'span'
            dic['items'] = []
            dic['items'].append(self.tunit2dic(start_time))
            dic['items'].append(self.tunit2dic(stop_time))
            return dic

        if self.isTimeSpan:
            if self.invalidSpan:
                dic['type'] = 'fuzzy'
                if re.match(r'^(最近|这|近|前)几(天|周|月|年)$',dic['raw']):
                    dic['norm'] = '近几'+dic['raw'][-1]
                else:
                    dic['norm'] = dic['raw']
            else:
                if self.isHoliday:
                    # 节日日期处理
                    holi_days = {'春节':(-1,5),'元旦':(0,0),'清明':(0,2),'劳动节':(0,4),'端午':(0,2),'中秋':(0,0),'国庆':(0,6)}
                    if self.isHoliday in holi_days:
                        start_shift = [0,0,holi_days[self.isHoliday][0]]
                        shift = [0,0,holi_days[self.isHoliday][1]]
                    else:
                        start_shift = [0,0,0]
                        shift = [0,0,1]
                    d = res[0].tp_origin.tunit
                    base_time = arrow.get(d[0],d[1],d[2])
                    start_time = base_time.shift(years=start_shift[0],months=start_shift[1],days=start_shift[2])
                    stop_time = base_time.shift(years=shift[0],months=shift[1],days=shift[2])
                    
                    start_time = [start_time.year,start_time.month,start_time.day,-1,-1,-1]
                    stop_time = [stop_time.year,stop_time.month,stop_time.day,-1,-1,-1]
                    dic['type'] = 'span'
                    dic['items'] = []
                    dic['items'].append(self.tunit2dic(start_time))
                    dic['items'].append(self.tunit2dic(stop_time))
                else:
                    dic['type'] = 'delta'
                    dic['items'] = [self.tunit2dic(res[0].tp_origin.tunit)]
        else:
            if len(res) == 0:
                dic['type'] = 'fuzzy'
                dic['norm'] = dic['raw']
            elif len(res) == 1:
                dic['type'] = 'point'
                dic['items'] = [self.tunit2dic(res[0].tp_origin.tunit)]
            else:
                dic['type'] = 'span'
                dic['items'] = []
                dic['items'].append(self.tunit2dic(res[0].tp_origin.tunit))
                dic['items'].append(self.tunit2dic(res[1].tp_origin.tunit))
        
        if dic['raw'].endswith('前后') or dic['raw'].endswith('左右'):
            for item in dic['items']:
                item['around'] = 'around'

        return dic

    def tunit2dic(self, tunit):
        res = {}
        time_scale = ['date', 'date', 'date', 'time', 'time', 'time']
        time_name = ['year', 'month', 'day', 'hour', 'minute', 'second']
        for scale, name, value in zip(time_scale, time_name, tunit):
            if value != -1:
                if scale not in res:
                    res[scale] = {}
                res[scale][name] = value
        return res

    def __preHandling(self):
        """
        待匹配字符串的清理空白符和语气助词以及大写数字转化的预处理
        :return:
        """
        self.target = StringPreHandler.delKeyword(self.target, u"\\s+")  # 清理空白符
        self.target = StringPreHandler.delKeyword(self.target, u"[的]+")  # 清理语气助词
        self.target = StringPreHandler.numberTranslator(self.target)  # 大写数字转化

    def __timeEx(self):
        """

        :param target: 输入文本字符串
        :param timeBase: 输入基准时间
        :return: TimeUnit[]时间表达式类型数组
        """
        startline = -1
        endline = -1
        rpointer = 0
        temp = []
        # print(self.target)
        match = self.pattern.finditer(self.target)
        for m in match:
            # print(m)
            startline = m.start()
            if startline == endline:
                rpointer -= 1
                temp[rpointer] = temp[rpointer] + m.group()
            else:
                temp.append(m.group())
            endline = m.end()
            rpointer += 1
        res = []
        # 时间上下文： 前一个识别出来的时间会是下一个时间的上下文，用于处理：周六3点到5点这样的多个时间的识别，第二个5点应识别到是周六的。
        contextTp = TimePoint()
        # print(self.timeBase)
        # print('temp',temp)
        for i in range(0, rpointer):
            # 这里是一个类嵌套了一个类
            res.append(TimeUnit(temp[i], self, contextTp))
            # res[i].tp.tunit[3] = -1
            contextTp = res[i].tp
            # print(self.nowTime.year)
            # print(contextTp.tunit)
        res = self.__filterTimeUnit(res)

        return res

    def __filterTimeUnit(self, tu_arr):
        """
        过滤timeUnit中无用的识别词。无用识别词识别出的时间是1970.01.01 00:00:00(fastTime=0)
        :param tu_arr:
        :return:
        """
        if (tu_arr is None) or (len(tu_arr) < 1):
            return tu_arr
        res = []
        for tu in tu_arr:
            if tu.time.timestamp != 0:
                res.append(tu)
        return res
