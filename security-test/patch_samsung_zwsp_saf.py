#!/usr/bin/env python3
from pathlib import Path
import sys

HELPER = r'''.class public final Les/v52s;
.super Ljava/lang/Object;

.method public static a()Z
    .locals 2
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
    const/16 v1, 0x23
    if-lt v0, v1, :cond_0
    const/4 v0, 0x1
    return v0
    :cond_0
    const/4 v0, 0x0
    return v0
.end method

.method public static b()Landroid/net/Uri;
    .locals 2
    new-instance v0, Les/c56$a;
    invoke-direct {v0}, Les/c56$a;-><init>()V
    const-string v1, "\\u200bAndroid"
    invoke-virtual {v0, v1}, Les/c56$a;->d(Ljava/lang/String;)Les/c56$a;
    move-result-object v0
    invoke-virtual {v0, v1}, Les/c56$a;->b(Ljava/lang/String;)Les/c56$a;
    move-result-object v0
    const/4 v1, 0x0
    invoke-virtual {v0, v1}, Les/c56$a;->c(Ljava/lang/String;)Les/c56$a;
    move-result-object v0
    invoke-virtual {v0}, Les/c56$a;->a()Landroid/net/Uri;
    move-result-object v0
    return-object v0
.end method

.method public static c(Ljava/lang/String;)Z
    .locals 7
    invoke-static {}, Les/v52s;->a()Z
    move-result v0
    const/4 v1, 0x0
    if-eqz v0, :cond_8
    if-eqz p0, :cond_8
    invoke-static {p0}, Les/up4;->m(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    if-eqz v0, :cond_8
    invoke-static {v0}, Les/up4;->c0(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v2
    if-nez v2, :cond_0
    const-string v2, "/storage/emulated/0"
    :cond_0
    const-string v3, "/"
    invoke-virtual {v2, v3}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v4
    if-eqz v4, :cond_1
    invoke-virtual {v2}, Ljava/lang/String;->length()I
    move-result v4
    add-int/lit8 v4, v4, -0x1
    invoke-virtual {v2, v1, v4}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v2
    :cond_1
    new-instance v4, Ljava/lang/StringBuilder;
    invoke-direct {v4}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {v4, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3
    invoke-virtual {v0, v3}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v4
    if-eqz v4, :cond_8
    invoke-virtual {v3}, Ljava/lang/String;->length()I
    move-result v3
    invoke-virtual {v0, v3}, Ljava/lang/String;->substring(I)Ljava/lang/String;
    move-result-object v0
    const-string v3, "Android/data"
    invoke-virtual {v0, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v4
    if-nez v4, :cond_7
    new-instance v4, Ljava/lang/StringBuilder;
    invoke-direct {v4}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {v4, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v5, "/"
    invoke-virtual {v4, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v4
    invoke-virtual {v0, v4}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v4
    if-nez v4, :cond_7
    const-string v3, "Android/obb"
    invoke-virtual {v0, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v4
    if-nez v4, :cond_7
    new-instance v4, Ljava/lang/StringBuilder;
    invoke-direct {v4}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {v4, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3
    invoke-virtual {v0, v3}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v0
    if-eqz v0, :cond_8
    :cond_7
    const/4 v0, 0x1
    return v0
    :cond_8
    return v1
.end method

.method public static d(Ljava/lang/String;)Landroid/net/Uri;
    .locals 8
    invoke-static {p0}, Les/v52s;->c(Ljava/lang/String;)Z
    move-result v0
    const/4 v1, 0x0
    if-eqz v0, :cond_4
    invoke-static {p0}, Les/up4;->m(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    invoke-static {v0}, Les/up4;->c0(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v2
    if-nez v2, :cond_0
    const-string v2, "/storage/emulated/0"
    :cond_0
    const-string v3, "/"
    invoke-virtual {v2, v3}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z
    move-result v4
    const/4 v5, 0x0
    if-eqz v4, :cond_1
    invoke-virtual {v2}, Ljava/lang/String;->length()I
    move-result v4
    add-int/lit8 v4, v4, -0x1
    invoke-virtual {v2, v5, v4}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v2
    :cond_1
    new-instance v4, Ljava/lang/StringBuilder;
    invoke-direct {v4}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {v4, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v2
    invoke-virtual {v2}, Ljava/lang/String;->length()I
    move-result v2
    invoke-virtual {v0, v2}, Ljava/lang/String;->substring(I)Ljava/lang/String;
    move-result-object v0
    new-instance v2, Ljava/lang/StringBuilder;
    invoke-direct {v2}, Ljava/lang/StringBuilder;-><init>()V
    const-string v3, "\\u200b"
    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v2, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0
    new-instance v2, Les/c56$a;
    invoke-direct {v2}, Les/c56$a;-><init>()V
    const-string v3, "\\u200bAndroid"
    invoke-virtual {v2, v3}, Les/c56$a;->d(Ljava/lang/String;)Les/c56$a;
    move-result-object v2
    invoke-virtual {v2, v0}, Les/c56$a;->b(Ljava/lang/String;)Les/c56$a;
    move-result-object v0
    invoke-virtual {v0, v1}, Les/c56$a;->c(Ljava/lang/String;)Les/c56$a;
    move-result-object v0
    invoke-virtual {v0}, Les/c56$a;->a()Landroid/net/Uri;
    move-result-object v0
    return-object v0
    :cond_4
    return-object v1
.end method

.method public static e()Z
    .locals 5
    invoke-static {}, Les/v52s;->a()Z
    move-result v0
    const/4 v1, 0x0
    if-eqz v0, :cond_3
    :try_start_0
    invoke-static {}, Lcom/estrongs/android/pop/FexApplication;->o()Lcom/estrongs/android/pop/FexApplication;
    move-result-object v0
    invoke-virtual {v0}, Landroid/content/Context;->getContentResolver()Landroid/content/ContentResolver;
    move-result-object v0
    invoke-virtual {v0}, Landroid/content/ContentResolver;->getPersistedUriPermissions()Ljava/util/List;
    move-result-object v0
    invoke-interface {v0}, Ljava/util/List;->iterator()Ljava/util/Iterator;
    move-result-object v0
    :cond_0
    invoke-interface {v0}, Ljava/util/Iterator;->hasNext()Z
    move-result v2
    if-eqz v2, :cond_3
    invoke-interface {v0}, Ljava/util/Iterator;->next()Ljava/lang/Object;
    move-result-object v2
    check-cast v2, Landroid/content/UriPermission;
    invoke-virtual {v2}, Landroid/content/UriPermission;->isReadPermission()Z
    move-result v3
    if-eqz v3, :cond_0
    invoke-virtual {v2}, Landroid/content/UriPermission;->getUri()Landroid/net/Uri;
    move-result-object v2
    invoke-static {v2}, Les/v52s;->g(Landroid/net/Uri;)Z
    move-result v2
    if-eqz v2, :cond_0
    const/4 v0, 0x1
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0
    return v0
    :catch_0
    move-exception v0
    :cond_3
    return v1
.end method

.method public static f(Ljava/lang/String;)Z
    .locals 1
    invoke-static {p0}, Les/v52s;->c(Ljava/lang/String;)Z
    move-result v0
    if-eqz v0, :cond_0
    invoke-static {}, Les/v52s;->e()Z
    move-result v0
    return v0
    :cond_0
    const/4 v0, 0x0
    return v0
.end method

.method public static g(Landroid/net/Uri;)Z
    .locals 3
    const/4 v0, 0x0
    if-eqz p0, :cond_1
    invoke-virtual {p0}, Landroid/net/Uri;->toString()Ljava/lang/String;
    move-result-object p0
    const-string v1, "\\u200bAndroid"
    invoke-static {v1}, Landroid/net/Uri;->encode(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    invoke-virtual {p0, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-nez v2, :cond_0
    const-string v1, "\\u200bAndroid"
    invoke-virtual {p0, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v2
    if-eqz v2, :cond_1
    :cond_0
    const/4 v0, 0x1
    :cond_1
    return v0
.end method

.method public static h(Landroid/net/Uri;)Landroid/net/Uri;
    .locals 3
    invoke-static {}, Les/v52s;->a()Z
    move-result v0
    if-eqz v0, :cond_3
    invoke-static {p0}, Les/v52s;->g(Landroid/net/Uri;)Z
    move-result v0
    if-eqz v0, :cond_3
    invoke-virtual {p0}, Landroid/net/Uri;->getLastPathSegment()Ljava/lang/String;
    move-result-object v0
    const-string v1, "children"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :cond_3
    const-string v0, "manage"
    invoke-virtual {p0, v0}, Landroid/net/Uri;->getQueryParameter(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    if-nez v1, :cond_3
    invoke-virtual {p0}, Landroid/net/Uri;->buildUpon()Landroid/net/Uri$Builder;
    move-result-object p0
    const-string v1, "1"
    invoke-virtual {p0, v0, v1}, Landroid/net/Uri$Builder;->appendQueryParameter(Ljava/lang/String;Ljava/lang/String;)Landroid/net/Uri$Builder;
    move-result-object p0
    invoke-virtual {p0}, Landroid/net/Uri$Builder;->build()Landroid/net/Uri;
    move-result-object p0
    :cond_3
    return-object p0
.end method
'''
HELPER = HELPER.replace('\\\\u200b', '\u200b')


def replace_once(text, old, new, name):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{name}: expected one match, got {n}')
    return text.replace(old, new, 1)


def replace_once_in_method(text, signature, old, new, name):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'{name}: method signature not found')
    end = text.find('.end method', start)
    if end < 0:
        raise RuntimeError(f'{name}: method end not found')
    segment = text[start:end]
    n = segment.count(old)
    if n != 1:
        raise RuntimeError(f'{name}: expected one method-local match, got {n}')
    segment = segment.replace(old, new, 1)
    return text[:start] + segment + text[end:]


def patch(root: Path):
    es = root / 'es'
    (es / 'v52s.smali').write_text(HELPER, encoding='utf-8')

    p = es / 'i41$h.smali'
    s = p.read_text(encoding='utf-8')
    marker = '    new-instance p1, Landroid/content/Intent;\n\n    const-string v0, "android.intent.action.OPEN_DOCUMENT_TREE"\n'
    injected = r'''    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v1, 0x23

    if-lt v0, v1, :v52_original_auth

    iget v0, p0, Les/i41$h;->f:I

    sget v1, Les/hc1$h;->o:I
    if-eq v0, v1, :v52_special_auth

    sget v1, Les/hc1$h;->p:I
    if-eq v0, v1, :v52_special_auth

    sget v1, Les/hc1$h;->r:I
    if-eq v0, v1, :v52_special_auth

    sget v1, Les/hc1$h;->s:I
    if-ne v0, v1, :v52_original_auth

    :v52_special_auth
    new-instance p1, Landroid/content/Intent;

    const-string v0, "android.intent.action.OPEN_DOCUMENT_TREE"
    invoke-direct {p1, v0}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V

    const/16 v0, 0xc3
    invoke-virtual {p1, v0}, Landroid/content/Intent;->setFlags(I)Landroid/content/Intent;

    const-string v0, "android.provider.extra.INITIAL_URI"
    invoke-static {}, Les/v52s;->b()Landroid/net/Uri;
    move-result-object v1
    invoke-virtual {p1, v0, v1}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Landroid/os/Parcelable;)Landroid/content/Intent;

    invoke-virtual {p0, p1}, Les/i41$h;->b(Landroid/content/Intent;)V
    return-void

    :v52_original_auth
    new-instance p1, Landroid/content/Intent;

    const-string v0, "android.intent.action.OPEN_DOCUMENT_TREE"
'''
    s = replace_once(s, marker, injected, 'i41 auth entry')
    p.write_text(s, encoding='utf-8')

    p = es / 'h41.smali'
    s = p.read_text(encoding='utf-8')
    marker = '''    invoke-static {v0}, Les/h41;->n(Ljava/lang/String;)Les/h41$c;

    move-result-object v2
'''
    injected = '''    invoke-static {v0}, Les/v52s;->f(Ljava/lang/String;)Z
    move-result v2
    if-eqz v2, :v52_p_normal

    invoke-static {v0}, Les/v52s;->d(Ljava/lang/String;)Landroid/net/Uri;
    move-result-object v2
    if-eqz v2, :v52_p_normal

    monitor-exit v1
    return-object v2

    :v52_p_normal
    invoke-static {v0}, Les/h41;->n(Ljava/lang/String;)Les/h41$c;

    move-result-object v2

    invoke-static {v0}, Les/v52s;->c(Ljava/lang/String;)Z
    move-result v15
    if-eqz v15, :v52_keep_old_grant

    invoke-static {}, Les/v52s;->e()Z
    move-result v15
    if-nez v15, :v52_keep_old_grant

    const/4 v2, 0x0

    :v52_keep_old_grant
'''
    s = replace_once(s, marker, injected, 'h41 p fastpath')

    marker = '''    new-instance v12, Les/h41$c;

    invoke-direct {v12}, Les/h41$c;-><init>()V
'''
    injected = '''    iget-object v6, v0, Les/hc1$h;->e:Landroid/net/Uri;
    invoke-static {v6}, Les/v52s;->g(Landroid/net/Uri;)Z
    move-result v6
    if-eqz v6, :v52_old_auth_validate

    iget-object v6, v0, Les/hc1$h;->e:Landroid/net/Uri;
    const/4 v10, 0x3
    invoke-virtual {v5, v6, v10}, Landroid/content/ContentResolver;->takePersistableUriPermission(Landroid/net/Uri;I)V

    const/4 v6, 0x1
    iput-boolean v6, v0, Les/hc1$h;->l:Z
    iput-boolean v3, v0, Les/hc1$c;->a:Z

    invoke-static/range {p0 .. p0}, Les/v52s;->d(Ljava/lang/String;)Landroid/net/Uri;
    move-result-object v6
    monitor-exit v1
    return-object v6

    :v52_old_auth_validate
    new-instance v12, Les/h41$c;

    invoke-direct {v12}, Les/h41$c;-><init>()V
'''
    s = replace_once(s, marker, injected, 'h41 p special auth return')

    marker = '''    invoke-static {}, Lcom/estrongs/android/pop/FexApplication;->o()Lcom/estrongs/android/pop/FexApplication;
'''
    injected = '''    invoke-static {p0}, Les/v52s;->h(Landroid/net/Uri;)Landroid/net/Uri;
    move-result-object p0

    invoke-static {}, Lcom/estrongs/android/pop/FexApplication;->o()Lcom/estrongs/android/pop/FexApplication;
'''
    s = replace_once_in_method(
        s,
        '.method public static query(Landroid/net/Uri;[Ljava/lang/String;)Landroid/database/Cursor;',
        marker,
        injected,
        'h41 query manage',
    )
    p.write_text(s, encoding='utf-8')

    p = es / 'oa5.smali'
    s = p.read_text(encoding='utf-8')
    marker = '''    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
'''
    injected = '''    invoke-static {p0}, Les/v52s;->f(Ljava/lang/String;)Z
    move-result v9
    if-eqz v9, :v52_oa5_c_normal
    invoke-static {p0}, Les/v52s;->d(Ljava/lang/String;)Landroid/net/Uri;
    move-result-object v9
    return-object v9

    :v52_oa5_c_normal
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
'''
    s = replace_once_in_method(
        s,
        '.method public static c(Ljava/lang/String;)Landroid/net/Uri;',
        marker,
        injected,
        'oa5 c',
    )

    marker = '''    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
'''
    injected = '''    invoke-static {p0}, Les/v52s;->f(Ljava/lang/String;)Z
    move-result v9
    if-eqz v9, :v52_oa5_e_normal
    invoke-static {p0}, Les/v52s;->d(Ljava/lang/String;)Landroid/net/Uri;
    move-result-object v9
    return-object v9

    :v52_oa5_e_normal
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
'''
    s = replace_once_in_method(
        s,
        '.method public static e(Ljava/lang/String;)Landroid/net/Uri;',
        marker,
        injected,
        'oa5 e',
    )

    marker = '''    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
'''
    injected = '''    invoke-static {p0}, Les/v52s;->c(Ljava/lang/String;)Z
    move-result v11
    if-eqz v11, :v52_oa5_l_normal

    invoke-static {}, Les/v52s;->e()Z
    move-result v11
    return v11

    :v52_oa5_l_normal
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
'''
    s = replace_once_in_method(
        s,
        '.method public static l(Ljava/lang/String;Ljava/util/List;)Z',
        marker,
        injected,
        'oa5 l authorization state',
    )
    p.write_text(s, encoding='utf-8')

    print('Samsung ZWSP one-shot SAF patch applied successfully')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: patch_samsung_zwsp_saf.py <smali_classes5_dir>')
    patch(Path(sys.argv[1]))

if __name__ == '__main__':
    main()
