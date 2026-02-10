#!/usr/bin/env python3
"""
Script pour convertir toutes les timelines flex vers tables HTML
"""

with open('/home/ubuntu/projects/carette/backend/email_templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern pour timeline_aller avec flexbox
old_aller = """timeline_aller = f'''
        {distance_label}
        <div style="display:flex;align-items:flex-start;margin-bottom:4px;">
            <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:32px;">
                <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
            </div>
            <div style="flex:1;margin-left:16px;padding-top:4px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:4px;">Départ</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;margin-bottom:4px;">
            <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:32px;">
                <div style="width:2px;height:32px;background:#e5e7eb;margin:0;"></div>
            </div>
            <div style="flex:1;margin-left:16px;">
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:32px;">
                <div style="width:32px;height:32px;border-radius:50%;background:{color_outbound};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
            </div>
            <div style="flex:1;margin-left:16px;padding-top:4px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:4px;">Arrivée</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
            </div>
        </div>
    '''"""

new_aller = """timeline_aller = f'''
        {distance_label}
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:4px;">
            <tr>
                <td width="32" valign="top" align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr><td width="32" height="32" style="border-radius:50%;background:{color_outbound};box-shadow:0 2px 4px rgba(0,0,0,0.1);text-align:center;vertical-align:middle;font-size:16px;line-height:32px;">🏠</td></tr>
                    </table>
                </td>
                <td width="16"></td>
                <td valign="top" style="padding-top:4px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:4px;">Départ</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
                </td>
            </tr>
        </table>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:4px;">
            <tr>
                <td width="32" valign="top" align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr><td width="2" height="32" style="background:#e5e7eb;"></td></tr>
                    </table>
                </td>
                <td width="16"></td>
                <td></td>
            </tr>
        </table>
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
                <td width="32" valign="top" align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr><td width="32" height="32" style="border-radius:50%;background:{color_outbound};box-shadow:0 2px 4px rgba(0,0,0,0.1);text-align:center;vertical-align:middle;font-size:16px;line-height:32px;">🏢</td></tr>
                    </table>
                </td>
                <td width="16"></td>
                <td valign="top" style="padding-top:4px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:4px;">Arrivée</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
                </td>
            </tr>
        </table>
    '''"""

count = content.count(old_aller)
print(f"Trouvé {count} occurrences de timeline_aller à remplacer")
content = content.replace(old_aller, new_aller)
print(f"Remplacé {count} occurrences")

# Pattern pour timeline_retour avec flexbox  
old_retour = """timeline_retour = f'''
        {distance_label}
        <div style="display:flex;align-items:flex-start;margin-bottom:4px;">
            <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:32px;">
                <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏢</div>
            </div>
            <div style="flex:1;margin-left:16px;padding-top:4px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:4px;">Départ</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;margin-bottom:4px;">
            <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:32px;">
                <div style="width:2px;height:32px;background:#e5e7eb;margin:0;"></div>
            </div>
            <div style="flex:1;margin-left:16px;">
            </div>
        </div>
        <div style="display:flex;align-items:flex-start;">
            <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:32px;">
                <div style="width:32px;height:32px;border-radius:50%;background:{color_return};display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">🏠</div>
            </div>
            <div style="flex:1;margin-left:16px;padding-top:4px;">
                <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:4px;">Arrivée</div>
                <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
            </div>
        </div>
    '''"""

new_retour = """timeline_retour = f'''
        {distance_label}
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:4px;">
            <tr>
                <td width="32" valign="top" align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr><td width="32" height="32" style="border-radius:50%;background:{color_return};box-shadow:0 2px 4px rgba(0,0,0,0.1);text-align:center;vertical-align:middle;font-size:16px;line-height:32px;">🏢</td></tr>
                    </table>
                </td>
                <td width="16"></td>
                <td valign="top" style="padding-top:4px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:4px;">Départ</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{destination}</div>
                </td>
            </tr>
        </table>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:4px;">
            <tr>
                <td width="32" valign="top" align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr><td width="2" height="32" style="background:#e5e7eb;"></td></tr>
                    </table>
                </td>
                <td width="16"></td>
                <td></td>
            </tr>
        </table>
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
                <td width="32" valign="top" align="center">
                    <table cellpadding="0" cellspacing="0" border="0">
                        <tr><td width="32" height="32" style="border-radius:50%;background:{color_return};box-shadow:0 2px 4px rgba(0,0,0,0.1);text-align:center;vertical-align:middle;font-size:16px;line-height:32px;">🏠</td></tr>
                    </table>
                </td>
                <td width="16"></td>
                <td valign="top" style="padding-top:4px;">
                    <div style="font-weight:600;color:#444;font-size:13px;margin-bottom:4px;">Arrivée</div>
                    <div style="color:#666;font-size:12px;line-height:1.4;word-wrap:break-word;overflow-wrap:break-word;">{departure}</div>
                </td>
            </tr>
        </table>
    '''"""

count2 = content.count(old_retour)
print(f"Trouvé {count2} occurrences de timeline_retour à remplacer")
content = content.replace(old_retour, new_retour)
print(f"Remplacé {count2} occurrences")

with open('/home/ubuntu/projects/carette/backend/email_templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTerminé! Total: {count + count2} remplacements")
