#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'JoshPaul'

import asyncio,logging,aiomysql

#创建基本日志函数，变量sql出现很多次，但我们还不知道它的作用
def log(sql,args=()):
    logging.info('SQL:%s' % sql)

#创建连接池
#异步IO起手式async，创建连接池函数，pool用法如下：
#https://aiomysql.readthedocs.io/en/latest/pool.html?highlight=create_pool
async def create_pool(loop,**kw):
    logging.info('create database connection pool...')
    #声明__pool为全局变量
    global __pool
    #使用这些基本参数来创建连接池
    #await和async是联动的（异步IO）
    __pool = await aiomysql.create_pool(
        host=kw.get('host','localhost'),
        port=kw.get('port',3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset','utf8'),
        autocommit=kw.get('autocommit',True),
        maxsize=kw.get('maxsize',10),
        minsize=kw.get('minsize',1),
        loop=loop
    )

#Select
async def select(sql,args,size=None):
    log(sql,args)
    global __pool
    #with-as：可以方便我们执行一些清理工作，如close和exit：
    #https://www.jianshu.com/p/c00df845323c

    #这里的await很多，可能看不懂什么意思，我暂时把它理解为：
    #可以让它后面执行的语句等一会，防止多个程序同时执行，达到异步效果
    with(await __pool) as conn:
        #cursor是游标,conn变量表示建立与数据库的连接。
        #'aiomysql.DictCursor'看似复杂，但它仅仅是要求返回字典格式。
        cur = await conn.cursor(aiomysql.DictCursor)
        #cursor游标实例调用execute来执行一条单独的SQL语句，参考自：
        # https://docs.python.org/zh-cn/3.8/library/sqlite3.html?highlight=execute#cursor-objects
        # 这里的 cur 来自上面的 conn.cursor ，然后执行后面的 sql ，具体sql干了啥先不管
        await cur.execute(sql.replace('?','%s'),args or())
        #size为空时为False,上面定义了初始值为None,具体得看传入的参数有没有定义size
        if size:
            #fetchmany可以获取行数为size的多行查询结果集，返回一个列表
            rs = await cur.fetchmany(size)
        else:
            #fetchall可以获取一个查询结果的所有(剩余)行,返回一个列表
            rs = await cur.fetchall()
        #close(),立即关闭cursor,从这一时刻起该cursor将不再可用
        await cur.close()
        #日志:提示返回了多少行
        logging.info('rows returned: %s' % len(rs))
        #现在终于知道了,select函数给我们从SQL返回了一个列表
        return rs

#Execute
async def execut(sql,args):
    log(sql)
    global __pool
    with (await __pool) as conn:
        try:
            cur = await conn.cursor()
            await cur.execute(sql.replace('?','%s'),args)
            #rowcount获取行数,应该表示的是该函数影响的行数
            affected = cur.rowcount
            await cur.close()
        except BaseException as_:
        #源码 except BaseException as e :反正不用这个e,改掉就不报错
            #将错误抛出,BaseException是异常不用管
            raise
        #返回行数
        return affected



